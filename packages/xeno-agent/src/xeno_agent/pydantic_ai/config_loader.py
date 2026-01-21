from pathlib import Path

import yaml

from xeno_agent.pydantic_ai.interfaces import ConfigLoader
from xeno_agent.pydantic_ai.models import AgentConfig, FlowConfig


class YAMLConfigLoader(ConfigLoader):
    def __init__(self, base_path: str | Path = "config"):
        self.base_path = Path(base_path)

    def load_agent_config(self, agent_id: str) -> AgentConfig:
        candidates = [self.base_path / f"{agent_id}.yaml", self.base_path / "agents" / f"{agent_id}.yaml"]

        for path in candidates:
            if path.exists():
                with path.open() as f:
                    data = yaml.safe_load(f)
                # If identifier is missing in yaml, inject it
                if "identifier" not in data:
                    data["identifier"] = agent_id
                return AgentConfig(**data)

        raise FileNotFoundError(f"Config for agent {agent_id} not found in {[str(p) for p in candidates]}")

    def load_flow_config(self, flow_id: str) -> FlowConfig:
        candidates = [self.base_path / f"{flow_id}.yaml", self.base_path / "flows" / f"{flow_id}.yaml"]

        for path in candidates:
            if path.exists():
                with path.open() as f:
                    data = yaml.safe_load(f)
                return FlowConfig(**data)

        raise FileNotFoundError(f"Flow config {flow_id} not found in {[str(p) for p in candidates]}")

    def list_agents(self) -> list[str]:
        # Simple scan
        agents = []
        search_paths = [self.base_path, self.base_path / "agents"]
        for p in search_paths:
            if p.exists():
                agents.extend(f.stem for f in p.glob("*.yaml"))
        return list(set(agents))
