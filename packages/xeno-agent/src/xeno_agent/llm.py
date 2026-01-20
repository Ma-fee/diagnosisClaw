"""
LLM factory and initialization for xeno-agent simulation.

Provides a centralized way to configure and create LLM instances using litellm.
"""

import os
from pathlib import Path
from typing import Any, Unpack

from dotenv import load_dotenv
from litellm import completion

from xeno_agent.utils.logging import get_logger

logger = get_logger(__name__)


def load_direnv_file(filepath: Path) -> None:
    """
    Manually parse a simple .envrc file (export KEY=VAL).
    """
    if not filepath.exists():
        return

    print(f"Loading environment from {filepath}")
    with filepath.open("r") as f:
        for line_content in f:
            line = line_content.strip()
            if not line or line.startswith("#"):
                continue

            # Remove 'export ' prefix if present
            if line.startswith("export "):
                line = line[7:].strip()

            # Simple split on first =
            if "=" in line:
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip()
                # Remove quotes
                if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                    val = val[1:-1]

                # Set if not already set (don't override existing env vars)
                if key not in os.environ:
                    os.environ[key] = val


# Try to find .envrc in common locations
# 1. Current working directory
# 2. Package root (where this file is located/../..)
# 3. Project root

current_dir = Path.cwd()
package_root = Path(__file__).parent.parent.parent
project_root = package_root.parent.parent

# Load .env first (standard)
# load_dotenv() searches for .env in current dir and parents by default if no path given,
# but here we want specific precedence.
load_dotenv()
load_dotenv(package_root / ".env")

# Load .envrc (custom support) - using load_dotenv as it supports 'export KEY=VAL' syntax
if (current_dir / ".envrc").exists():
    load_dotenv(current_dir / ".envrc")

if package_root != current_dir and (package_root / ".envrc").exists():
    load_dotenv(package_root / ".envrc")

# Default configuration
DEFAULT_API_BASE = "http://api.ai.rootcloud.info/v1"
DEFAULT_MODEL = "svc/glm-4.7"
DEFAULT_PROVIDER = "openai"  # Use openai-compatible interface


def get_llm_config(
    api_base: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    **kwargs: Unpack[Any],
) -> dict[str, Any]:
    """
    Create a configuration dict for LLM initialization.

    Args:
        api_base: The base URL for the LLM API (default: from env or DEFAULT_API_BASE)
        model: The model name to use (default: from env or DEFAULT_MODEL)
        api_key: The API key for authentication (default: from env)
        **kwargs: Additional parameters for LLM configuration (temperature, max_tokens, etc.)

    Returns:
        Configuration dictionary compatible with CrewAI's LLM initialization
    """
    # Priority: explicit param > environment variable > default constant
    config = {
        "api_base": api_base or os.getenv("XENO_LLM_API_BASE", DEFAULT_API_BASE),
        "model": (model or os.getenv("XENO_LLM_MODEL", DEFAULT_MODEL)),  # Full model name with provider
        "api_key": api_key or os.getenv("XENO_LLM_API_KEY", ""),
        **kwargs,
    }

    # Set reasonable defaults if not provided
    if "temperature" not in kwargs:
        config["temperature"] = 0.7
    if "max_tokens" not in kwargs:
        config["max_tokens"] = 2000

    return config


def get_model_identifier(model: str | None = None) -> str:
    """
    Get the model identifier in the format litellm expects (provider/model).

    Args:
        model: The model name to use (from env, param, or default)

    Returns:
        A string in format "provider/model"
    """
    model_name = model or os.getenv("XENO_LLM_MODEL", DEFAULT_MODEL)

    # If the model already has a provider prefix, return as-is
    if "/" in model_name:
        return model_name

    # Otherwise, prepend the default provider (openai/ for OpenAI-compatible APIs)
    return f"{DEFAULT_PROVIDER}/{model_name}"


def create_crewai_llm(
    api_base: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    **kwargs: Unpack[Any],
) -> str:
    """
    Create a CrewAI-compatible LLM instance.

    Args:
        api_base: The base URL for LLM API
        model: The model name to use
        api_key: The API key for authentication
        **kwargs: Additional parameters (temperature, max_tokens, etc.)

    Returns:
        Model identifier string for CrewAI LLM initialization
    """
    # Get configuration

    # Convert model name to liteLLM format (provider/model)
    return get_model_identifier(model)

    # Set environment variables for LiteLLM (used by CrewAI internally)
    # CrewAI/LiteLLM defaults to looking for OPENAI_API_BASE/KEY for openai-compatible providers

    # Return the model name string

    # The adapter below is deprecated in favor of CrewAI's native string support
    # class LiteLLMAdapter: ...


def test_connection(api_base: str | None = None, model: str | None = None, api_key: str | None = None) -> bool:
    """
    Test the connection to LLM API.

    Args:
        api_base: The base URL for LLM API
        model: The model name to use
        api_key: The API key for authentication

    Returns:
        True if connection successful, False otherwise
    """
    config = get_llm_config(api_base=api_base, model=model, api_key=api_key)
    lite_llm_model = get_model_identifier(model)

    try:
        response = completion(
            model=lite_llm_model,
            messages=[{"role": "user", "content": "Hello, this is a connection test."}],
            api_base=config["api_base"],
            api_key=config.get("api_key") or None,
            max_tokens=10,
        )
        logger.info(f"✓ Connection test successful. Model: {lite_llm_model}")
        logger.info(f"  Response: {response['choices'][0]['message']['content']}")
        return True
    except Exception as e:
        logger.error(f"✗ Connection test failed: {e}")
        return False
