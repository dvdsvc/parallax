"""External, role-scoped request adapter; native source and routing stay intact."""
from contextlib import contextmanager
from copy import deepcopy
import json
from pathlib import Path
from threading import Lock

from langchain_core.messages import SystemMessage
from langchain_core.runnables import Runnable, RunnableLambda
from langchain_core.runnables.config import ensure_config, merge_configs

from common import digest, ROOT, UPSTREAM

HERE = Path(__file__).resolve().parent
MARKER = "[TALKHIER GLOBAL ORGANIZATIONAL ARCHITECTURE]"
SCOPES = ("evaluation_supervisor", "all_roles")
_INSTALL_LOCK = Lock()


def verify_artifacts(domain):
    manifest = json.loads((HERE / "manifest.json").read_text())
    if manifest["native_upstream_commit"] != UPSTREAM:
        raise RuntimeError("Organization description uses a different upstream commit")
    for name, expected in manifest["source_files_sha256"].items():
        if digest(ROOT / name) != expected:
            raise RuntimeError(f"Audited native source changed: {name}")
    for name, expected in manifest["artifact_files_sha256"].items():
        if digest(HERE / name) != expected:
            raise RuntimeError(f"Frozen organization artifact changed: {name}")
    filename = f"global_organizational_architecture_v2_{domain}.txt"
    if filename not in manifest["artifact_files_sha256"]:
        raise ValueError(f"Unaudited domain: {domain}")
    text = (HERE / filename).read_text()
    if not text.startswith(MARKER):
        raise RuntimeError("Organization description marker missing")
    return text, manifest


class ModelView(Runnable):
    def __init__(self, delegate, role, text, selected, observe=None):
        self.delegate, self.role, self.text = delegate, role, text
        self.selected, self.observe = selected, observe

    def metadata(self, phase):
        # Callback metadata stays outside provider messages and parameters.
        return {"talkhier_role": self.role, "talkhier_phase": phase,
                "organization_awareness_v2": self.selected}

    def prepare(self, value, phase):
        messages = value.to_messages() if hasattr(value, "to_messages") else list(value)
        messages = deepcopy(messages)
        existing = [m for m in messages if isinstance(m, SystemMessage) and str(m.content).startswith(MARKER)]
        if existing:
            raise RuntimeError("Organization description already present in native inputs")
        if self.selected:
            messages.insert(0, SystemMessage(content=self.text))
        if self.observe:
            self.observe({"role": self.role, "phase": phase, "injected": self.selected,
                          "messages": [{"type": m.type, "name": m.name, "content": m.content,
                                        **({"tool_calls": m.tool_calls} if getattr(m, "tool_calls", None) else {})}
                                       for m in messages]})
        return messages

    def invoke(self, input, config=None, **kwargs):
        config = merge_configs(ensure_config(config), {"metadata": self.metadata("model")})
        return self.delegate.invoke(self.prepare(input, "model"), config, **kwargs)

    async def ainvoke(self, input, config=None, **kwargs):
        config = merge_configs(ensure_config(config), {"metadata": self.metadata("model")})
        return await self.delegate.ainvoke(self.prepare(input, "model"), config, **kwargs)

    def bind_tools(self, tools, **kwargs):
        return ModelView(self.delegate.bind_tools(tools, **kwargs), self.role,
                         self.text, self.selected, self.observe)

    def with_structured_output(self, schema, **kwargs):
        # Preserve the delegate's native schema/provider options unchanged.
        return RunnableLambda(lambda value: self.prepare(value, "structured")) | self.delegate.with_structured_output(
            schema, **kwargs).with_config(metadata=self.metadata("structured"))


@contextmanager
def install(domain, condition="BASE", scope="all_roles", observe=None):
    if condition not in ("BASE", "V2") or scope not in SCOPES:
        raise ValueError("Unknown condition or role scope")
    text, manifest = verify_artifacts(domain)
    from multiagent.agent_team import AgentTeam, ReactAgent
    original_supervisor = AgentTeam.loadSuperviser
    original_member = ReactAgent.loadMember
    if not _INSTALL_LOCK.acquire(blocking=False):
        raise RuntimeError("Use one organization condition per process; overlapping installations are unsupported")

    def view(model, role):
        selected = condition == "V2" and (scope == "all_roles" or role == "Evaluator Supervisor")
        return ModelView(model, role, text, selected, observe)

    def supervisor(self, *args, **kwargs):
        self.llm = view(self.llm, self.team_name + " Supervisor")
        return original_supervisor(self, *args, **kwargs)

    def member(self, name, *args, **kwargs):
        original_model = self.llm
        self.llm = view(original_model, name)
        try:
            return original_member(self, name, *args, **kwargs)
        finally:
            self.llm = original_model

    AgentTeam.loadSuperviser, ReactAgent.loadMember = supervisor, member
    try:
        yield {"condition": condition, "organization_awareness_v2": condition == "V2",
               "scope": scope, "organization_prompt_sha256": digest(HERE / f"global_organizational_architecture_v2_{domain}.txt"),
               "organization_manifest_sha256": digest(HERE / "manifest.json"),
               "reference_roma_v2_sha256": manifest["reference_roma_v2_sha256"],
               "placement": "first system message before each selected native model call",
               "native_source_modified": bool(manifest.get("provider_compatibility_changes")),
               "provider_compatibility_files": sorted(manifest.get("provider_compatibility_changes", {})),
               "agent_architecture_modified": False}
    finally:
        AgentTeam.loadSuperviser, ReactAgent.loadMember = original_supervisor, original_member
        _INSTALL_LOCK.release()
