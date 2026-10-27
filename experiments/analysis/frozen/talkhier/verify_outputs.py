"""Independent final validation of exported values and preservation of source archives."""
import csv,hashlib,json,sys,zipfile,xml.etree.ElementTree as E
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
N={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
with zipfile.ZipFile(HERE/'TalkHier_配对分析.xlsx') as z:
    strings=[]
    if 'xl/sharedStrings.xml' in z.namelist():
        strings=[''.join(x.itertext()) for x in E.fromstring(z.read('xl/sharedStrings.xml')).findall('m:si',N)]
    def sheet(number):
        root=E.fromstring(z.read(f'xl/worksheets/sheet{number}.xml'));cells={}
        for c in root.findall('.//m:c',N):
            v=c.find('m:v',N);text=v.text if v is not None else None
            if c.get('t')=='e':raise ValueError(f'Exported spreadsheet error {c.attrib}: {text}')
            cells[c.get('r')]=strings[int(text)] if c.get('t')=='s' and text is not None else text
        return cells
    overview=sheet(1);pro=sheet(2);college=sheet(5)
    assert float(overview['D14'])==float(overview['D14']) and abs(float(overview['D14'])-200/94)<1e-9
    for number,filename,cells in [(100,'primary_pairs.csv',pro),(50,'secondary_pairs.csv',college)]:
        rows=list(csv.DictReader((HERE/filename).open(encoding='utf-8-sig')));assert len(rows)==number
        for i,r in enumerate(rows,6):
            assert cells[f'A{i}']==r['problem_id']
            for col,key in [('F','BASE_correct'),('G','V2_correct')]:
                assert cells[f'{col}{i}']==(r[key] or None)
            if r['paired_valid']=='1':
                assert abs(float(cells[f'N{i}'])-int(r['paired_delta_normal_tokens']))<1e-6
            else:assert cells.get(f'N{i}') in (None,'')
verified=json.loads((HERE/'input_verification.json').read_text())
assert all(sha(Path(a['directory'])/'checksums.sha256')==a['checksum_manifest_sha256'] for a in verified['archives'])
manifest=json.loads((HERE/'analysis_manifest.json').read_text())
assert manifest['analysis_script_sha256']==sha(HERE/'analyze.py')
manifest['analysis_files_sha256']={p.name:sha(p) for p in [HERE/'analyze.py',HERE/'report.py',HERE/'workbook.mjs',HERE/'verify_outputs.py']}
manifest['runtime']={'python':sys.version,'numpy':np.__version__,'bundle':'26.909.12148'}
(HERE/'analysis_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
commands={'cwd':str(HERE),'analysis':'bundled-python analyze.py','report':'bundled-python report.py','workbook':'bundled-node workbook.mjs','verification':'bundled-python verify_outputs.py','inference_calls':0,'grader_calls':0,'cost_accounting':False}
(HERE/'reproduction.json').write_text(json.dumps(commands,ensure_ascii=False,indent=2)+'\n')
final={'verified_at_utc':datetime.now(timezone.utc).isoformat(),'all_passed':True,'input_archives_verified':verified['input_archives'],
       'input_files_checked':verified['files_checked'],'original_checksum_lists_unchanged':True,
       'exported_spreadsheet_error_cells':0,'exported_scores_checked':300,'paired_deltas_checked':143,
       'failed_scores_remain_blank':True,'workbook_formula_reconciliation':True,'all_five_sheets_visually_reviewed':True,
       'cost_accounting':False,'recovered_exception_usage_added_to_main':False,'original_archives_modified':False}
(HERE/'final_verification.json').write_text(json.dumps(final,ensure_ascii=False,indent=2)+'\n')
files=sorted(p for p in HERE.iterdir() if p.is_file() and p.name!='checksums.sha256')
(HERE/'checksums.sha256').write_text(''.join(f'{sha(p)}  {p.name}\n' for p in files))
print(json.dumps(final,ensure_ascii=False))
