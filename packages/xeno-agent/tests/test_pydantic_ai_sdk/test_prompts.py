from xeno_agent.pydantic_ai.models import AgentConfig, FlowConfig
from xeno_agent.pydantic_ai.prompts import PromptBuilder


def test_prompt_layering():
    agent_config = AgentConfig(identifier="qa", role="QA", backstory="Backstory content.", when_to_use="Always")
    flow_config = FlowConfig(
        name="Flow",
        description="Desc",
        entry_agent="qa",
        participants=["qa"],
        global_instructions="Global Context content.",
        delegation_rules={"qa": {"allow_delegation_to": ["fault_expert"]}},
    )

    builder = PromptBuilder(agent_config, flow_config)
    prompt = builder.build_system_prompt()

    assert "Role: QA" in prompt
    assert "Backstory content." in prompt
    assert "Global Context content." in prompt
    assert "fault_expert" in prompt
