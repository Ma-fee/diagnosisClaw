"""
Tests for LLM factory and initialization.
"""

from unittest.mock import patch

from xeno_agent.simulation import create_crewai_llm, get_llm_config


def test_get_llm_config_defaults():
    """Test get_llm_config with default values."""
    config = get_llm_config()

    assert "model" in config
    assert "api_base" in config
    assert "temperature" in config
    assert "max_tokens" in config
    assert config["temperature"] == 0.7
    assert config["max_tokens"] == 2000


def test_get_llm_config_custom():
    """Test get_llm_config with custom values."""
    from unittest.mock import patch

    with patch.dict(
        "os.environ",
        {
            "XENO_LLM_MODEL": "custom_model",
            "XENO_LLM_API_BASE": "http://custom.api",
        },
    ):
        config = get_llm_config()

        assert "custom_model" in config["model"]
        assert "custom.api" in config["api_base"]


def test_get_llm_config_explicit_params():
    """Test that explicit params override environment."""
    config = get_llm_config(api_base="http://explicit.api", model="explicit_model")

    assert config["api_base"] == "http://explicit.api"
    assert config["model"] == "explicit_model"


def test_create_crewai_llm():
    """Test creating a CrewAI LLM instance."""
    llm = create_crewai_llm(model="test_model", api_base="http://test.api")

    assert llm is not None
    assert hasattr(llm, "config")
    assert llm.config["model"] == "test_model"


def test_llm_adapter_has_invoke():
    """Test that the LLM adapter has an invoke method."""
    llm = create_crewai_llm(model="test_model")

    assert hasattr(llm, "invoke")
    assert callable(llm.invoke)


@patch("xeno_agent.simulation.llm.completion")
def test_llm_adapter_invoke(mock_completion):
    """Test that the LLM adapter's invoke method calls litellm."""
    mock_completion.return_value = {"choices": [{"message": {"content": "test response"}}]}

    llm = create_crewai_llm(model="test_model")
    response = llm.invoke(messages=[{"role": "user", "content": "test"}])

    mock_completion.assert_called_once()
    assert hasattr(response, "content")
    assert response.content == "test response"
