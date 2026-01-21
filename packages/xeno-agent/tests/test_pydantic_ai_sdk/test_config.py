import pytest
import yaml

from xeno_agent.pydantic_ai.config_loader import YAMLConfigLoader
from xeno_agent.pydantic_ai.models import AgentConfig, FlowConfig


@pytest.fixture
def sample_agent_yaml(tmp_path):
    path = tmp_path / "qa_assistant.yaml"
    content = {
        "identifier": "qa_assistant",
        "type": "main",
        "role": "QA Assistant",
        "backstory": "You help users.",
        "when_to_use": "General questions",
        "allow_delegation_to": ["fault_expert"],
        "tools": {"mode": "allowlist", "builtins": ["search"], "external": []},
        "skills": ["dialogue_management"],
    }
    path.write_text(yaml.dump(content))
    return path


@pytest.fixture
def sample_flow_yaml(tmp_path):
    path = tmp_path / "fault_diagnosis.yaml"
    content = {
        "name": "Fault Diagnosis",
        "description": "SOP",
        "entry_agent": "qa_assistant",
        "participants": ["qa_assistant", "fault_expert"],
        "global_instructions": "Follow protocol",
        "delegation_rules": {"qa_assistant": {"allow_delegation_to": ["fault_expert"]}},
    }
    path.write_text(yaml.dump(content))
    return path


def test_load_agent_config(sample_agent_yaml):
    loader = YAMLConfigLoader(base_path=sample_agent_yaml.parent)
    config = loader.load_agent_config("qa_assistant")

    assert isinstance(config, AgentConfig)
    assert config.identifier == "qa_assistant"
    assert config.role == "QA Assistant"
    assert config.tools.mode == "allowlist"
    assert "fault_expert" in config.allow_delegation_to


def test_load_flow_config(sample_flow_yaml):
    loader = YAMLConfigLoader(base_path=sample_flow_yaml.parent)
    config = loader.load_flow_config("fault_diagnosis")

    assert isinstance(config, FlowConfig)
    assert config.entry_agent == "qa_assistant"
    assert config.delegation_rules["qa_assistant"]["allow_delegation_to"] == ["fault_expert"]
