#!/usr/bin/env python3
"""Offline, question-level PLS on immutable native-derived behavior panels.

No agent, provider, or grader calls. Outputs belong to a NEW analysis archive.
"""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('OMP_NUM_THREADS', '1')
os.environ.setdefault('MPLCONFIGDIR', '/private/tmp/roma-behavior-pls-matplotlib')
import argparse
import hashlib
import json
import platform
import shutil
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import warnings
import numpy as np
import scipy
from scipy.stats import pearsonr, spearmanr
import sklearn
from sklearn.cross_decomposition import PLSRegression
from sklearn.model_selection import KFold

SEED = 20261005
MAX_COMPONENTS = 10
PRIMARY = [
    'SEAL0_joint_candidate_pool',
    'SEAL0_behavior_independent_all94',
    'FRAMES_behavior_independent',
]
SENSITIVITY = [
    'SEAL0_joint_logtoken_sensitivity',
    'FRAMES_logtoken_sensitivity',
    'SEAL0_joint_complete3_sensitivity',
]
LABELS = {
    PRIMARY[0]: 'SEAL0：行为＋协作评分',
    PRIMARY[1]: 'SEAL0：仅行为、全部94题',
    PRIMARY[2]: 'FRAMES：仅行为',
    SENSITIVITY[0]: 'SEAL0：log-token敏感性',
    SENSITIVITY[1]: 'FRAMES：log-token敏感性',
    SENSITIVITY[2]: 'SEAL0：三轮齐全敏感性',
}

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1048576), b''):
            h.update(block)
    return h.hexdigest()

def save(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n')

def verify_sums(root, allowed_mismatches=()):
    lines = (root / 'SHA256SUMS').read_text().splitlines()
    mismatches = []
    for line in lines:
        digest, name = line.split(maxsplit=1)
        name = name.lstrip('*')
        actual = sha(root / name)
        if actual != digest:
            assert name in allowed_mismatches, ('source checksum mismatch', name)
            mismatches.append({'file': name, 'expected': digest, 'actual': actual})
    return {'files': len(lines), 'mismatches': mismatches}

def preprocess(x):
    mean = x.mean(axis=0)
    sd = x.std(axis=0, ddof=1)
    nonconstant = np.flatnonzero(sd > 1e-12)
    z = (x[:, nonconstant] - mean[nonconstant]) / sd[nonconstant]
    kept = []
    rank = 0
    for j in range(z.shape[1]):
        trial = z[:, kept + [j]]
        new_rank = np.linalg.matrix_rank(trial, tol=1e-9)
        if new_rank > rank:
            kept.append(j)
            rank = new_rank
    columns = nonconstant[kept]
    return {'columns': columns, 'mean': mean, 'sd': sd, 'rank': rank}, z[:, kept]

def transform(x, prep):
    c = prep['columns']
    return (x[:, c] - prep['mean'][c]) / prep['sd'][c]

def prep_json(prep, names):
    c = prep['columns'].tolist()
    return {'columns': c, 'features': [names[j] for j in c],
            'dropped': [s for j, s in enumerate(names) if j not in c],
            'train_mean': prep['mean'].tolist(), 'train_sample_sd': prep['sd'].tolist(),
            'rank': int(prep['rank'])}

def fit_path(z, y, ztest, maxk=MAX_COMPONENTS):
    # Public sequential PLS coefficients: a k-component prefix equals fitting k.
    k = min(maxk, z.shape[1], z.shape[0] - 1)
    if k < 1 or np.std(y) < 1e-12:
        return np.full((len(ztest), maxk), np.mean(y))
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore', message='y residual is constant')
        model = PLSRegression(n_components=k, scale=False, max_iter=1000, tol=1e-8).fit(z, y)
    centered = ztest - z.mean(axis=0)
    pred = []
    for n in range(1, maxk + 1):
        use = min(n, k)
        beta = model.x_rotations_[:, :use] @ model.y_loadings_[:, :use].T
        pred.append((centered @ beta).ravel() + np.mean(y))
    return np.column_stack(pred)

def inner_select(x, y, seed):
    losses = []
    splits = KFold(n_splits=4, shuffle=True, random_state=seed)
    for train, test in splits.split(x):
        prep, z = preprocess(x[train])
        p = fit_path(z, y[train], transform(x[test], prep))
        losses.append(np.mean((p - y[test, None]) ** 2, axis=0))
    losses = np.asarray(losses)
    average = losses.mean(axis=0)
    best = int(np.argmin(average))
    se = losses[:, best].std(ddof=1) / np.sqrt(len(losses))
    one_se = int(np.flatnonzero(average <= average[best] + se)[0]) + 1
    return best + 1, {'mse_by_components': average.tolist(), 'one_se_components': one_se}

def metrics(y, predictions, baselines):
    yy = np.broadcast_to(y, predictions.shape)
    err = np.mean((predictions - yy) ** 2)
    nullerr = np.mean((baselines - yy) ** 2)
    average = predictions.mean(axis=0)
    r = float(pearsonr(average, y).statistic) if np.std(average) > 1e-12 else None
    rs = float(spearmanr(average, y).statistic) if np.std(average) > 1e-12 else None
    return {'Q2_vs_train_mean': float(1 - err / nullerr),
            'out_of_fold_R2': float(1 - err / np.var(y)),
            'RMSE_pp': float(100 * np.sqrt(err)),
            'MAE_pp': float(100 * np.mean(abs(predictions - yy))),
            'mean_baseline_RMSE_pp': float(100 * np.sqrt(nullerr)),
            'ensemble_OOF_pearson_r': r, 'ensemble_OOF_spearman_r': rs,
            'ensemble_OOF_RMSE_pp': float(100 * np.sqrt(np.mean((average - y) ** 2))),
            'ensemble_OOF_Q2': float(1 - np.mean((average - y) ** 2) /
                                        np.mean((baselines.mean(axis=0) - y) ** 2))}

def nested_cv(x, y, names, repeats=10, details=True):
    predictions, baselines, fold_ids = [], [], []
    selection, audits = [], []
    for repeat in range(repeats):
        pred = np.empty(len(y)); baseline = np.empty(len(y)); ids = np.empty(len(y), dtype=int)
        outer = KFold(n_splits=5, shuffle=True, random_state=SEED + repeat)
        for fold, (train, test) in enumerate(outer.split(x)):
            innerseed = SEED + 1000 + repeat * 10 + fold
            k, curve = inner_select(x[train], y[train], innerseed)
            prep, z = preprocess(x[train])
            pred[test] = fit_path(z, y[train], transform(x[test], prep))[:, k - 1]
            baseline[test] = np.mean(y[train]); ids[test] = fold
            selection.append(k)
            if details:
                audits.append({'repeat': repeat, 'outer_fold': fold,
                               'train_indices': train.tolist(), 'test_indices': test.tolist(),
                               'inner_seed': innerseed, 'selected_components': k,
                               'inner_cv': curve, 'preprocessing': prep_json(prep, names)})
        predictions.append(pred); baselines.append(baseline); fold_ids.append(ids)
    predictions = np.asarray(predictions); baselines = np.asarray(baselines)
    return {'metrics': metrics(y, predictions, baselines),
            'selected_components_counts': dict(sorted(Counter(selection).items())),
            'predictions': predictions.tolist(), 'mean_baseline_predictions': baselines.tolist(),
            'outer_fold_ids': np.asarray(fold_ids).tolist(), 'fold_audits': audits}

def fit_final(x, y, k):
    prep, z = preprocess(x)
    used = min(k, z.shape[1], z.shape[0] - 1)
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore', message='y residual is constant')
        model = PLSRegression(n_components=used, scale=False, max_iter=1000, tol=1e-8).fit(z, y)
    beta = np.zeros(x.shape[1]); beta[prep['columns']] = model.coef_.ravel()
    component_ss = np.sum(model.x_scores_ ** 2, axis=0) * np.sum(model.y_loadings_ ** 2, axis=0)
    w2 = model.x_weights_ ** 2
    norm = np.sum(w2, axis=0)
    vip_used = np.sqrt(len(prep['columns']) *
                       np.sum(w2 / np.maximum(norm, 1e-30) * component_ss, axis=1) /
                       max(float(component_ss.sum()), 1e-30))
    vip = np.zeros(x.shape[1]); vip[prep['columns']] = vip_used
    return prep, z, model, beta, vip

def run_dataset(name, source, out, permutations, bootstraps):
    print('START', name, flush=True)
    inputs = json.loads((source / (name + '_behavior_inputs.json')).read_text())
    performance = json.loads((source / (name + '_performance.json')).read_text())
    outcomes = {r['question_id']: r for r in performance['question_outcomes']}
    qids = [r['question_id'] for r in inputs]
    assert len(qids) == len(set(qids)) and set(qids) == set(outcomes)
    names = list(inputs[0]['deltas_V2_minus_BASE'])
    assert all(list(r['deltas_V2_minus_BASE']) == names for r in inputs)
    x = np.array([[r['deltas_V2_minus_BASE'][f] for f in names] for r in inputs])
    y = np.array([outcomes[q]['delta_BASE_minus_V2'] for q in qids])
    assert np.isfinite(x).all() and np.isfinite(y).all()
    assert all(abs(outcomes[q]['BASE_accuracy'] - outcomes[q]['V2_accuracy'] - y[i]) < 1e-12
               for i, q in enumerate(qids)), 'Outcome sign or pairing mismatch'
    panel = [{'question_id': q, 'rounds': r['rounds'], 'paired_rounds': r['paired_rounds'],
              'features_V2_minus_BASE': r['deltas_V2_minus_BASE'],
              'performance_BASE_minus_V2': float(y[i]),
              'BASE_accuracy': outcomes[q]['BASE_accuracy'],
              'V2_accuracy': outcomes[q]['V2_accuracy']} for i, (q, r) in enumerate(zip(qids, inputs))]
    folder = out / name; folder.mkdir()
    save(folder / 'question_panel.json', panel)
    # Verify the public coefficient prefix shortcut against separate native fits.
    prep, z = preprocess(x)
    path = fit_path(z, y, z)
    diffs = []
    for k in range(1, MAX_COMPONENTS + 1):
        m = PLSRegression(n_components=k, scale=False, max_iter=1000, tol=1e-8).fit(z, y)
        diffs.append(float(np.max(abs(m.predict(z).ravel() - path[:, k-1]))))
    assert max(diffs) < 1e-8, ('prefix mismatch', name, diffs)
    cv = nested_cv(x, y, names)
    save(folder / 'nested_cv.json', cv)
    print('CV', name, json.dumps(cv['metrics']), flush=True)
    k, curve = inner_select(x, y, SEED + 9000)
    prep, z, model, beta, vip = fit_final(x, y, k)
    fitted = model.predict(z).ravel()
    full = {'selected_components': k, 'selection_cv': curve,
            'preprocessing': prep_json(prep, names),
            'in_sample_R2': float(1 - np.sum((fitted-y)**2) / np.sum((y-y.mean())**2)),
            'in_sample_pearson_r': float(pearsonr(fitted, y).statistic),
            'fitted_predictions': fitted.tolist(),
            'x_weights': model.x_weights_.tolist(), 'x_loadings': model.x_loadings_.tolist(),
            'x_rotations': model.x_rotations_.tolist(), 'x_scores': model.x_scores_.tolist(),
            'y_loadings': model.y_loadings_.tolist(), 'target_mean': float(y.mean()),
            'prefix_vs_separate_fit_max_abs_error': max(diffs)}
    rng = np.random.default_rng(SEED + 20000)
    perm_q2 = []
    groups = np.array([r['paired_rounds'] for r in inputs])
    fixed_observed = metrics(y, np.array(cv['predictions'])[:1],
                            np.array(cv['mean_baseline_predictions'])[:1])
    for b in range(permutations):
        perm_y = y.copy()
        for group in np.unique(groups):
            loc = np.flatnonzero(groups == group)
            perm_y[loc] = rng.permutation(y[loc])
        perm = nested_cv(x, perm_y, names, repeats=1, details=False)
        perm_q2.append(perm['metrics']['Q2_vs_train_mean'])
        if (b + 1) % 50 == 0:
            print('PERM', name, b+1, '/', permutations, flush=True)
    perm_result = {'permutations': permutations,
                   'observed_fixed_split_Q2': fixed_observed['Q2_vs_train_mean'],
                   'stratification': 'permute Y within paired_rounds count strata',
                   'component_selection_repeated_for_every_permutation': True,
                   'null_Q2': perm_q2,
                   'p_upper_tail': float((1 + sum(v >= fixed_observed['Q2_vs_train_mean'] for v in perm_q2)) /
                                         (permutations + 1)) if permutations else None}
    save(folder / 'permutation.json', perm_result)
    rng = np.random.default_rng(SEED + 30000)
    bs_beta, bs_vip = [], []
    for b in range(bootstraps):
        loc = rng.integers(0, len(y), len(y))
        if np.std(y[loc]) < 1e-12:
            continue
        _, _, _, betab, vipb = fit_final(x[loc], y[loc], k)
        bs_beta.append(betab); bs_vip.append(vipb)
    bb = np.asarray(bs_beta); vv = np.asarray(bs_vip)
    variables = []
    for j, feature in enumerate(names):
        variables.append({'feature': feature, 'retained_full_fit': j in prep['columns'],
                          'VIP': float(vip[j]), 'coefficient_pp_per_1SD': float(100*beta[j]),
                          'coefficient_conditional_bootstrap95_pp': (100*np.quantile(bb[:, j], [.025,.975])).tolist(),
                          'VIP_conditional_bootstrap95': np.quantile(vv[:, j], [.025,.975]).tolist(),
                          'bootstrap_sign_agreement': float(np.mean(np.sign(bb[:,j]) == np.sign(beta[j])))})
    variables.sort(key=lambda row: -row['VIP'])
    full['variables'] = variables
    full['bootstrap_note'] = 'Question resamples; refit preprocessing and PLS; fixed full-data selected component count. Conditional descriptive stability, not post-selection confidence intervals.'
    full['bootstrap_successful'] = len(bs_beta)
    save(folder / 'full_fit_descriptive.json', full)
    save(folder / 'conditional_bootstrap_coefficients.json',
         {'features': names, 'components_fixed': k, 'coefficients': bb.tolist(), 'VIP': vv.tolist()})
    result = {'name': name, 'label': LABELS[name], 'questions': len(y),
              'matched_rounds': sum(r['paired_rounds'] for r in inputs),
              'candidate_features': len(names), 'full_fit_retained_features': len(prep['columns']),
              'BASE_accuracy': performance['BASE_accuracy'], 'V2_accuracy': performance['V2_accuracy'],
              'target_mean_BASE_minus_V2': float(y.mean()),
              'target_sd': float(y.std(ddof=1)), 'cv': cv['metrics'],
              'outer_selection_counts': cv['selected_components_counts'],
              'full_fit_components': k, 'in_sample_R2': full['in_sample_R2'],
              'permutation': {key: val for key, val in perm_result.items() if key != 'null_Q2'},
              'top_variables_descriptive': variables[:8]}
    save(folder / 'summary.json', result)
    # Standalone scientific figure: leave-question-out predictions, no API.
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.5), layout='constrained')
    avg = np.mean(np.asarray(cv['predictions']), axis=0)
    ax[0].scatter(y*100, avg*100, alpha=.65, s=28)
    lim = np.array([min(y.min(), avg.min())-0.1, max(y.max(),avg.max())+0.1])*100
    ax[0].plot(lim,lim,'--', color='gray', linewidth=1)
    ax[0].set(xlabel='Observed BASE - V2 performance (pp)',
              ylabel='Repeated nested-CV prediction (pp)',
              title=f'Out-of-fold Q2={cv["metrics"]["Q2_vs_train_mean"]:.3f}')
    top = list(reversed(variables[:8]))
    ax[1].barh([v['feature'] for v in top], [v['VIP'] for v in top], color='#386cb0')
    ax[1].axvline(1,color='gray',linestyle='--',linewidth=1)
    ax[1].set(xlabel='Full-fit VIP (descriptive)', title=f'{k} PLS components; training R2={full["in_sample_R2"]:.3f}')
    fig.suptitle(name)
    fig.savefig(folder / 'pls.png', dpi=180); fig.savefig(folder / 'pls.svg'); plt.close(fig)
    print('DONE', name, 'p', perm_result['p_upper_tail'], flush=True)
    return result

def report(out, results, manifest):
    lines = ['# 以 performance 差值为目标的 PLS 监督分析', '',
             'X 为题级行为变化（V2−BASE），Y 为同题同轮正确率差（BASE−V2）。同题先合并有效匹配轮次，再题目等权。Y<0表示V2更好；没有把同题不同轮分进训练和测试两侧。PLS是行为与结果的关联分析，不是提前预测尚未运行的题目，也不是因果中介分析。', '',
             '采用10次重复的5折外层交叉验证，训练集内部4折在1–10成分中按最小MSE选择。常数/完全线性别名处理与标准化均仅用相应训练折；保留近共线变量。对照为每个外层训练集的Y均值，预测值不裁剪。Q²=1−PLS的测试SSE/训练均值对照的测试SSE，负值表示没有胜过均值预测。', '',
             '| 集合 | 题/匹配轮 | 全样本成分 | 样本内R² | 外层Q² | 外层RMSE / 均值对照（pp） | 固定分折置换p / Holm |',
             '|---|---:|---:|---:|---:|---:|---:|']
    for r in results:
        c=r['cv']; p=r['permutation']['p_upper_tail']
        lines.append(f'| {r["label"]} | {r["questions"]}/{r["matched_rounds"]} | {r["full_fit_components"]} | {r["in_sample_R2"]:.3f} | {c["Q2_vs_train_mean"]:.3f} | {c["RMSE_pp"]:.2f} / {c["mean_baseline_RMSE_pp"]:.2f} | {p:.3f} / {r["permutation"]["p_Holm_three_primary"]:.3f} |' if p is not None else
                     f'| {r["label"]} | {r["questions"]}/{r["matched_rounds"]} | {r["full_fit_components"]} | {r["in_sample_R2"]:.3f} | {c["Q2_vs_train_mean"]:.3f} | {c["RMSE_pp"]:.2f} / {c["mean_baseline_RMSE_pp"]:.2f} | 未检验 |')
    lines += ['', '前三项为主分析，后三项为预先固定的敏感性分析。每组使用自己的有效题目集合，不能把联合评分86题与此前三轮完整86题混同。置换仅对三项主分析执行199次，按每题有效匹配轮数分层置换Y；每次完整重做内部成分选择，用同一固定外层5折的Q²比较。主表Q²则平均10次外层重复。置换p是探索性检验，三项主分析家族另给Holm校正。', '']
    for r in results[:3]:
        lines += [f'## {r["label"]}', '',
                  f'有效题数{r["questions"]}；BASE→V2正确率 {100*r["BASE_accuracy"]:.2f}%→{100*r["V2_accuracy"]:.2f}%。候选变量{r["candidate_features"]}个，全样本去除常数和完全线性别名后{r["full_fit_retained_features"]}个。外层各成分数选择次数：`{r["outer_selection_counts"]}`。', '',
                  '| 变量 | 全样本VIP | 标准化系数（pp/1SD） | 系数条件bootstrap95% | 符号保持比例 |',
                  '|---|---:|---:|---:|---:|']
        for v in r['top_variables_descriptive']:
            lo,hi=v['coefficient_conditional_bootstrap95_pp']
            lines.append(f'| {v["feature"]} | {v["VIP"]:.2f} | {v["coefficient_pp_per_1SD"]:+.2f} | [{lo:+.2f}, {hi:+.2f}] | {100*v["bootstrap_sign_agreement"]:.1f}% |')
        lines += ['', '系数为控制其他保留变量后的描述性权重：正系数表示相应V2−BASE行为量增加时，预测BASE−V2差值更正。共线变量的系数会抵消，不能逐项解释为因果贡献。VIP>1不是显著性标准。500次题级bootstrap重新拟合标准化和PLS，但固定全样本成分数；这些区间未包含成分选择不确定性，也不能取代外层验证。', '', f'![PLS]({out/r["name"]/"pls.png"})', '']
    lines += ['## 解释边界与留档', '',
              '监督学习会主动寻找与Y相关的方向，因此样本内R²和相关性不能用来证明机制。主判断是留出题目的预测误差；即使Q²为负，也只说明本样本、候选变量和该线性模型没有可验证的预测收益，不证明任何单个真实机制不存在。SEAL0存在重复轮数与协作评分覆盖差异，FRAMES仅47有效配对且来自运行后的预算收缩子集；这些限制不能靠PLS消除。没有填补失败或超限分数，没有删除普通极端值。', '',
              'token是已记录原生usage，不是轨迹文本长度或账单；weighted_depth包含全部逻辑节点，root深度0；真实重复工具动作保留。沿用已冻结PCA输入及其原生事件核算口径。未修改PCA及此前任何轨迹或评分归档，未进行任何Agent/API/judge调用。', '',
              f'执行commit：`{manifest["script_commit"]}`。检查源PCA归档{manifest["source_checksum_files"]}个列名文件，既存差异仅为文字report.md（哈希见source_archive_checksum_audit.json）；全部用于PLS的行为与结果数据均通过旧清单校验，前后哈希不变。没有重写旧哈希清单。各数据集保存题级输入、每次外层划分、训练预处理、内部选择曲线、留出预测、置换零分布和全样本描述模型。依赖版本、脚本快照、Git bundle与SHA256SUMS在本目录。']
    (out/'report.md').write_text('\n'.join(lines)+'\n')
    per=['# PLS 题级观测与留出预测', '', '预测为10次重复外层留出预测的均值，仅用于逐题查看；主报告误差按全部重复预测计算。单位为百分点，负值表示V2更好。', '']
    for r in results[:3]:
        folder=out/r['name']
        panel=json.loads((folder/'question_panel.json').read_text())
        cv=json.loads((folder/'nested_cv.json').read_text())
        avg=np.mean(cv['predictions'],axis=0)
        per += [f'## {r["label"]}', '', '| 题号 | 有效匹配轮数 | 观测BASE−V2 | PLS留出预测 |', '|---|---:|---:|---:|']
        per += [f'| {v["question_id"]} | {v["paired_rounds"]} | {100*v["performance_BASE_minus_V2"]:+.2f} | {100*avg[i]:+.2f} |' for i,v in enumerate(panel)]
        per += ['']
    (out/'per_question.md').write_text('\n'.join(per)+'\n')

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('source',type=Path); parser.add_argument('output',type=Path)
    args=parser.parse_args(); source=args.source.resolve(); out=args.output.resolve()
    assert not out.exists(), 'Refuse to overwrite an existing analysis archive'
    source_audit=verify_sums(source, allowed_mismatches=('report.md',))
    count=source_audit['files']
    out.mkdir(parents=True)
    script=Path(__file__).resolve(); repo=script.parent
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
    assert subprocess.check_output(['git','status','--porcelain'],cwd=repo,text=True).strip() == '', 'Commit script before running'
    sources={str(source/(n+suffix)):sha(source/(n+suffix)) for n in PRIMARY+SENSITIVITY
             for suffix in ['_behavior_inputs.json','_performance.json']}
    plan={'created_utc':datetime.now(timezone.utc).isoformat(), 'seed':SEED,
          'primary_datasets':PRIMARY,'sensitivity_datasets':SENSITIVITY,
          'X':'question mean V2 minus BASE behavior differences; full frozen candidate pool',
          'Y':'question mean BASE_correct minus V2_correct, same matched rounds as X',
          'outer_cv':'10 repetitions x 5 folds; question disjoint; fixed seeds',
          'inner_cv':'4 folds within each outer training set; components 1..10; minimum MSE, tie smaller',
          'preprocessing':'training-only sample SD standardization; remove constants/exact linear aliases; retain near-correlated columns',
          'permutation':'199, one fixed nested 5x4-fold split; Y permuted within matched-round-count strata; repeat model selection',
          'bootstrap':'500 question resamples, fixed full-data component count; descriptive conditional coefficient/VIP stability',
          'source_archive':str(source), 'no_agent_api_judge_calls':True}
    save(out/'analysis_plan.json',plan); save(out/'source_sha256.json',sources)
    save(out/'source_archive_checksum_audit.json',source_audit)
    shutil.copy2(script,out/'analysis_script.snapshot.py')
    subprocess.run(['git','bundle','create',str(out/'analysis_scripts.bundle'),'--all'],cwd=repo,check=True)
    subprocess.run(['git','bundle','verify',str(out/'analysis_scripts.bundle')],cwd=repo,check=True,stdout=subprocess.DEVNULL)
    manifest={'script_commit':commit,'script_sha256':sha(script),'source_checksum_files':count,
              'runtime':{'python':platform.python_version(),'numpy':np.__version__,
                         'scipy':scipy.__version__,'scikit_learn':sklearn.__version__}}
    save(out/'manifest.json',manifest)
    results=[]
    for name in PRIMARY+SENSITIVITY:
        results.append(run_dataset(name,source,out,199 if name in PRIMARY else 0,500))
        save(out/'results.partial.json',results)
    p=np.array([r['permutation']['p_upper_tail'] for r in results[:3]])
    order=np.argsort(p); adjusted=np.empty(3); previous=0
    for pos,index in enumerate(order):
        previous=max(previous,min(1.,(3-pos)*p[index])); adjusted[index]=previous
    for i in range(3):
        results[i]['permutation']['p_Holm_three_primary']=float(adjusted[i])
    save(out/'results.json',results)
    report(out,results,manifest)
    for path,digest in sources.items():
        assert sha(path)==digest,('source changed',path)
    assert verify_sums(source, allowed_mismatches=('report.md',))==source_audit
    save(out/'completion_verification.json',{'completed_utc':datetime.now(timezone.utc).isoformat(),
         'source_hashes_unchanged':True,'source_archive_checksum_audit':source_audit,
         'script_commit':commit,'datasets_completed':len(results),'no_agent_api_judge_calls':True})
    files=sorted(p for p in out.rglob('*') if p.is_file() and p.name!='SHA256SUMS')
    (out/'SHA256SUMS').write_text(''.join(f'{sha(p)}  {p.relative_to(out)}\n' for p in files))
    checked=verify_sums(out)
    print('COMPLETE',out,'verified_files',checked,flush=True)

if __name__=='__main__':
    main()
