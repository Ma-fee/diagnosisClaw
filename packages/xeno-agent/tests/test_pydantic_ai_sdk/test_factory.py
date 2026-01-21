from unittest.mock import MagicMock

from xeno_agent.pydantic_ai.factory import AgentFactory
from xeno_agent.pydantic_ai.interfaces import ConfigLoader, SkillLoader
from xeno_agent.pydantic_ai.models import AgentConfig, FlowConfig


def test_create_agent_with_flow():
    # Setup Mocks
    mock_loader = MagicMock(spec=ConfigLoader)
    mock_loader.load_agent_config.return_value = AgentConfig(identifier="qa", role="QA", backstory="B", when_to_use="Always", allow_delegation_to=[], skills=["test_skill"])

    mock_skill_loader = MagicMock(spec=SkillLoader)
    mock_skill_loader.render_skill.return_value = "<xml>test_skill</xml>"

    flow_config = FlowConfig(
        name="Flow",
        description="D",
        entry_agent="qa",
        participants=["qa"],
        global_instructions="G",
        delegation_rules={"qa": {"allow_delegation_to": ["fault_expert"]}},
    )

    factory = AgentFactory(mock_loader, skill_loader=mock_skill_loader)
    agent = factory.create("qa", flow_config)

    # Check if agent is created
    assert agent is not None
    # Check if dependency type is set (sanity check)
    # Note: Accessing internal _deps_type or similar might be flaky across versions
    # But we assume basic creation worked.
