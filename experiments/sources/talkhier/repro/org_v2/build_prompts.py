"""Generate TalkHier static descriptions in the current ROMA V2 format.

Uses previously audited native organization specifications. No agent/model calls.
The diagram shows allowed communication relations, not a question execution trace.
"""
import hashlib
import json
from pathlib import Path
import sys

OUT = Path(__file__).resolve().parent
REPO = OUT.parents[1]
ROMA_V2 = OUT / "roma_v2_reference.txt"
sys.path.insert(0, str(REPO / "src"))
from prompts.mmlu import getPrompts
DOMAINS = ("moral_scenarios", "college_physics", "machine_learning", "formal_logic", "us_foreign_policy")
ROLE_DESCRIPTIONS = {
    "Intent": "Evaluates the purpose and intent behind the action.",
    "Normality": "Evaluates how normal the action is in ordinary daily behavior.",
    "Responsibility": "Evaluates whether the action fulfills the relevant responsibilities.",
    "Well-being": "Evaluates the action's effects on the well-being of those involved.",
    "Physics": "Evaluates the correctness of the answer's physics reasoning and assumptions.",
    "Mathematics": "Evaluates the correctness of the answer's calculations and mathematical steps.",
    "Answer Consistency": "Evaluates consistency between the selected answer choice and its explanation.",
    "Machine Learning": "Evaluates whether the answer applies machine-learning concepts correctly.",
    "Statistical Soundness": "Evaluates the statistical validity of the answer and its reasoning.",
    "Truth Table": "Evaluates the correctness of truth-table reasoning when applicable.",
    "Counterexample": "Evaluates the correctness of counterexamples when applicable.",
    "Predicate Logic": "Evaluates the syntactic and semantic correctness of predicate-logic translations.",
    "Logical Argument": "Evaluates the relationship between premises, reasoning, and the identified conclusion.",
    "Formal Logic": "Evaluates whether formal-logic notation faithfully represents the intended meaning.",
    "Factual Accuracy": "Evaluates the correctness of the historical and economic facts implied by the answer.",
    "Policy Alignment": "Evaluates consistency with the relevant documented policies and agreements.",
    "Conceptual Clarity": "Evaluates the meaning, scope, and distinguishing features of the concepts used in the answer.",
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generate(domain):
    specification = getPrompts(domain, {"question": "Static roster extraction", "choices": ["A", "B", "C", "D"]})
    members = [k for k, v in specification["team"]["Evaluator"].items() if isinstance(v, dict)]
    diagram = [
        "                     Current Task",
        "                          |",
        "                          v",
        "                  Default Supervisor ------------> FINISH",
        "                          |",
        "                          +<--> Answer Generator",
        "                          |",
        "                          +<--> Revisor",
        "                          |",
        "                          +<--> Evaluator Supervisor",
    ]
    for member in members:
        diagram.extend(["                                       |", f"                                       +<--> {member}"])
    roles = [
        ("Default Supervisor", "The root supervisor coordinates Answer Generator, Revisor, and Evaluator Supervisor. It selects among its direct members, receives their returned outputs, and can finish the main-team execution through FINISH."),
        ("Answer Generator", "A direct member of Default Supervisor that produces a candidate answer for the supplied task and returns it to Default Supervisor."),
        ("Revisor", "A direct member of Default Supervisor that receives an answer and evaluation feedback, revises the answer when needed, and returns the revision and any request for re-evaluation to Default Supervisor."),
        ("Evaluator Supervisor", "A subordinate supervisor under Default Supervisor that coordinates its direct evaluation members, collects their evaluation results, and reports the results and a summary to Default Supervisor."),
    ]
    roles.extend((member, "An evaluation member under Evaluator Supervisor. " + ROLE_DESCRIPTIONS[member]
                  + " Returns its evaluation to Evaluator Supervisor.") for member in members)
    text = (
        "[TALKHIER GLOBAL ORGANIZATIONAL ARCHITECTURE]\n\n"
        "The following describes the global architecture of TalkHier for this configured domain. It is a static description of how the organization processes tasks in general. It does not determine which path will be taken for the current task.\n\n"
        "ORGANIZATIONAL FLOW\n```text\n" + "\n".join(diagram) + "\n```\n\n"
        "Each two-way connection represents a supervisor's dispatch route to a direct member and that member's return route to the supervisor. FINISH is the completion route of the main team.\n\n"
        "A team invocation enters its supervisor first. After a direct member completes, the graph returns to that team's supervisor before another direct member is selected. Returning from the evaluation team passes through Evaluator Supervisor to Default Supervisor.\n\n"
        "ROLE RESPONSIBILITIES\n\n" + "\n\n".join(name + "\n" + description for name, description in roles) + "\n\n"
        "GLOBAL INFORMATION FLOW\n\n"
        "Dispatch and return:\nSupervisors route work to their direct members. Answer Generator and Revisor return their outputs to Default Supervisor. Evaluation members return their results to Evaluator Supervisor, which reports the evaluation results and their summary to Default Supervisor.\n\n"
        "Evaluation and revision:\nDefault Supervisor can send a candidate answer to Evaluator Supervisor for evaluation and can pass the answer and evaluation feedback to Revisor. Revisor returns its revised answer and any request for re-evaluation to Default Supervisor.\n\n"
        "Feedback:\nDefault Supervisor can route a revised answer back through Evaluator Supervisor and its members for another evaluation. This feedback passes through Default Supervisor rather than a direct connection between Revisor and the evaluation members.\n\n"
        "Scheduling:\nEach supervisor selects one next member at a time. Direct-member invocations are serial within their team, and the main team waits for a selected evaluation-team invocation to return. Evaluation members do not have a fixed sibling order or direct sibling dispatch routes. This implementation has no separate subtask dependency DAG.\n\n"
        "Declared workflow requirements:\nThe native main-team prompt requires contacting Answer Generator first and contacting Revisor before FINISH. A modified answer leads to a request for re-evaluation; when Default Supervisor requests re-evaluation, the evaluation-supervisor prompt requires re-evaluating with all its members. These are native prompt requirements. The graph itself does not check that these members have been visited before permitting its return or completion routes.\n\n"
        + ("Domain-specific workflow requirements:\nFor Formal Logic, the task prompt states that execution finishes only when all evaluation results are positive. The evaluation-supervisor prompt also calls for selecting Truth Table or Counterexample when the corresponding method is involved. These are prompt requirements rather than extra graph gates.\n\n" if domain == "formal_logic" else "") +
        "INTERPRETATION\n\n"
        "TalkHier has a main team with a nested evaluation branch. Default Supervisor can select Answer Generator, Revisor, Evaluator Supervisor, or FINISH. Evaluator Supervisor can select one of its direct evaluation members or return to Default Supervisor. Leaf members return through their assigned supervisor. These relations describe the available organization and information flow.\n\n"
        "This architecture description provides knowledge of the organization as a whole. It does not specify the current task's concrete execution trace, selected evaluator order, number of evaluation or revision rounds, answer content, or future execution state. The native prompt-level workflow requirements described above remain applicable.\n"
    )
    assert all(member in text for member in members)
    assert all(heading in text for heading in ("ORGANIZATIONAL FLOW", "ROLE RESPONSIBILITIES", "GLOBAL INFORMATION FLOW", "INTERPRETATION"))
    assert all(phrase not in text for phrase in ("Correctness Score", "three of the four", "NEVER SHOW", "MUST OUTPUT", "Fixture A", "Static roster extraction"))
    file = OUT / f"global_organizational_architecture_v2_{domain}.txt"
    file.write_text(text)
    return file


def main():
    source_manifest = json.loads((REPO / "repro" / "workspace_manifest.json").read_text())
    for record in source_manifest["upstream_files"]:
        assert digest(REPO / record["path"]) == record["sha256"], record["path"]
    files = [generate(domain) for domain in DOMAINS]
    manifest = {
        "native_upstream_commit": source_manifest["upstream_commit"],
        "reference_roma_v2_sha256": digest(ROMA_V2),
        "reference_roma_v2": "repro/org_v2/roma_v2_reference.txt",
        "reference_form": "ASCII text diagram plus fixed headings and natural-language role/flow descriptions",
        "source_files_sha256": {r["path"]: r["sha256"] for r in source_manifest["upstream_files"]},
        "source_role_descriptions": "src/prompts/mmlu.py:14-113; high-level summaries only",
        "artifact_files_sha256": {p.name: digest(p) for p in [*files, OUT / "build_prompts.py", ROMA_V2]},
        "paid_model_calls": 0, "native_source_modified": False,
        "status": "Frozen descriptions for an external BASE/V2 adapter; no real model benchmark",
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print("Generated and checked five V2-aligned candidate descriptions; no model calls.")


if __name__ == "__main__":
    main()
