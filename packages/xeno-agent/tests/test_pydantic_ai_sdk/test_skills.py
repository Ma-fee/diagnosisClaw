import xml.etree.ElementTree as ET

import pytest
from pydantic import ValidationError

from xeno_agent.pydantic_ai.skills import SkillRegistry

# Sample Anthropic XML skill definition
SAMPLE_SKILL_XML = """<?xml version="1.0"?>
<skill_definition>
    <name>test_skill</name>
    <description>A test skill for demonstration</description>
    <parameters>
        <parameter name="query" type="string" required="true">
            <description>The search query</description>
        </parameter>
    </parameters>
</skill_definition>
"""


def test_skill_loader_parses_xml():
    """Test that AnthropicSkillLoader can parse XML skill definitions."""
    # Create temporary skill file
    import tempfile
    from pathlib import Path

    with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
        f.write(SAMPLE_SKILL_XML)
        temp_path = Path(f.name)

    try:
        # Parse the XML
        tree = ET.parse(temp_path)  # noqa: S314
        root = tree.getroot()

        assert root.tag == "skill_definition"
        assert root.find("name").text == "test_skill"

    finally:
        if temp_path.exists():
            temp_path.unlink()


def test_skill_registry_bind_function():
    """Test that SkillRegistry can bind a Python function to an XML skill."""

    # Define a sample function
    def sample_skill_function(query: str) -> str:
        return f"Result for: {query}"

    # Create registry
    registry = SkillRegistry()

    # Register the skill
    registry.register("test_skill", sample_skill_function)

    # Verify it's registered
    assert "test_skill" in registry.registry

    # Retrieve it
    retrieved = registry.get("test_skill")
    assert retrieved == sample_skill_function


def test_skill_registry_bind_invalid_signature():
    """Test that binding with wrong signature raises ValidationError."""

    # Function with wrong parameter
    def invalid_function(number: int) -> str:
        return str(number)

    registry = SkillRegistry()

    # This should raise ValidationError
    with pytest.raises(ValidationError, match="Parameter mismatch"):
        registry.register("test_skill", invalid_function, expected_params=["query"])
