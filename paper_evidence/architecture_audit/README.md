# Architecture and visibility evidence for Figure 1 and Section 7.1

This revision uses the implemented task-processing and context-construction code, not a paper-level sketch alone. The existing native ROMA source snapshots match commit a6e3bb4f9e0694375fa627fa4b8bf8cae50592a6 and still match their original files. TalkHier team and prompt snapshots come from the actual MMLU-Pro Physics batch startup source. The original snapshots and recorded hashes were checked before copying. Representative model-input records are retained separately; their source notes distinguish historical runs and the stopped ROMA budget pilot. These inputs establish disclosure, not comparative behavior effects.

Figure 1 shows an illustrative ROMA task tree and the configured TalkHier Physics role tree. A blue Executor call is on the illustrated direct-execution branch, while the other task branch supplies the deeper subtasks. The four modules inside a task are reusable functions, not a sequence that every task must execute. The depth cap may bypass Atomizer and Planner. The TalkHier blue roster is relative to Evaluator Supervisor; separate rows identify root and leaf inputs. Green panels summarize the actual static description and add no graph edges, permissions, or live task tree. No disclosure percentages or outcome estimates appear in the figure.

Section 7.1 separates architectural facts from an explanatory hypothesis. Task-centric versus role-centric input construction and different permitted adjustments are directly visible in code. Their contribution to the observed utility differences is not independently identified by this study; the hypothesized value depends on existing information, usable actions and the task environment. Existing outcome estimates and behavioral results remain unchanged.

| Figure / discussion claim | Frozen code anchor |
| --- | --- |
| ROMA: depth cap and state machine | [async def _async_execute_state_machine](sources/roma/native/src/roma_dspy/core/engine/solve.py) (line 944) |
| ROMA: module-specific native contexts | [async def _execute_agent_with_tracing](sources/roma/native/src/roma_dspy/core/engine/runtime.py) (line 400) |
| ROMA: child depth and dependencies | [def _create_subtask_graph](sources/roma/native/src/roma_dspy/core/engine/runtime.py) (line 917) |
| ROMA: direct child results and dependency readiness | [def _collect_subtask_results](sources/roma/native/src/roma_dspy/core/engine/runtime.py) (line 1000) |
| ROMA: objective and recursion fields | [def _build_fundamental](sources/roma/native/src/roma_dspy/core/context/manager.py) (line 99) |
| ROMA: conditional dependency results | [async def _build_executor_specific](sources/roma/native/src/roma_dspy/core/context/manager.py) (line 171) |
| TalkHier: local roster, job list and routing choices | [def loadSuperviser](sources/talkhier/frozen/src/multiagent/agent_team.py) (line 48) |
| TalkHier: fixed team edges and supervisor returns | [def createStateGraph](sources/talkhier/frozen/src/multiagent/agent_team.py) (line 175) |
| TalkHier: leaf instructions, background and selected history | [def loadMember](sources/talkhier/frozen/src/multiagent/agent_team.py) (line 280) |
| TalkHier: nested team construction | [def buildTeam](sources/talkhier/frozen/src/multiagent/agent_team.py) (line 385) |
| TalkHier Physics: two-expert roster | [elif domain == "college_physics"](sources/talkhier/frozen/src/prompts/mmlu.py) (line 26) |
| ORG-DESC: same native interfaces, inserted system description | [def prepare](sources/talkhier/adapter.py) (line 49) |

The source manifest records every copied file and SHA256. All code was read as text; no agent runtime, model, search, or grader was invoked. The shared figure geometry produces PNG, vector PDF, editable SVG text, and standalone inline TikZ.
