"""Tests for load_tool_schema utility."""

import json
import tempfile
from pathlib import Path

import pytest
import yaml

from xeno_agent.utils.tool_schema import load_tool_schema


class TestLoadToolSchema:
    """Test suite for load_tool_schema function."""

    def test_returns_none_when_path_is_none(self) -> None:
        """Test that None is returned when path is None."""
        result = load_tool_schema(None)
        assert result is None

    def test_raises_file_not_found_when_file_doesnt_exist(self) -> None:
        """Test that FileNotFoundError is raised when file doesn't exist."""
        with pytest.raises(FileNotFoundError, match="Tool schema file not found"):
            load_tool_schema("/nonexistent/path/to/file.yaml")

    def test_loads_yaml_file_correctly(self) -> None:
        """Test that YAML files are loaded correctly."""
        schema = {
            "name": "test_tool",
            "description": "A test tool",
            "parameters": {
                "type": "object",
                "properties": {"param1": {"type": "string"}},
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(schema, f)
            temp_path = f.name

        try:
            result = load_tool_schema(temp_path)
            assert result == schema
        finally:
            Path(temp_path).unlink()

    def test_loads_yml_file_correctly(self) -> None:
        """Test that .yml files are loaded correctly."""
        schema = {"name": "test_tool", "version": "1.0"}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            yaml.dump(schema, f)
            temp_path = f.name

        try:
            result = load_tool_schema(temp_path)
            assert result == schema
        finally:
            Path(temp_path).unlink()

    def test_loads_json_file_correctly(self) -> None:
        """Test that JSON files are loaded correctly."""
        schema = {
            "name": "test_tool",
            "description": "A test tool",
            "parameters": {
                "type": "object",
                "properties": {"param1": {"type": "integer"}},
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(schema, f)
            temp_path = f.name

        try:
            result = load_tool_schema(temp_path)
            assert result == schema
        finally:
            Path(temp_path).unlink()

    def test_accepts_string_path(self) -> None:
        """Test that string paths are accepted."""
        schema = {"name": "test_tool"}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(schema, f)
            temp_path = f.name

        try:
            result = load_tool_schema(temp_path)  # type: ignore[arg-type]
            assert result == schema
        finally:
            Path(temp_path).unlink()

    def test_accepts_path_object(self) -> None:
        """Test that Path objects are accepted."""
        schema = {"name": "test_tool"}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(schema, f)
            temp_path = f.name

        try:
            result = load_tool_schema(Path(temp_path))
            assert result == schema
        finally:
            Path(temp_path).unlink()

    def test_raises_value_error_on_invalid_yaml(self) -> None:
        """Test that ValueError is raised for invalid YAML."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("invalid: yaml: content:\n  - [unclosed")
            temp_path = f.name

        try:
            with pytest.raises(ValueError, match="Failed to parse tool schema file"):
                load_tool_schema(temp_path)
        finally:
            Path(temp_path).unlink()

    def test_raises_value_error_on_invalid_json(self) -> None:
        """Test that ValueError is raised for invalid JSON."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"invalid": json content}')
            temp_path = f.name

        try:
            with pytest.raises(ValueError, match="Failed to parse tool schema file"):
                load_tool_schema(temp_path)
        finally:
            Path(temp_path).unlink()

    def test_treats_unknown_extension_as_json_then_yaml(self) -> None:
        """Test that files with unknown extensions are tried as JSON then YAML."""
        schema = {"name": "test_tool"}

        # Test with .txt extension - should try JSON first, fall back to YAML
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            yaml.dump(schema, f)
            temp_path = f.name

        try:
            result = load_tool_schema(temp_path)
            assert result == schema
        finally:
            Path(temp_path).unlink()

    def test_handles_complex_yaml_structure(self) -> None:
        """Test that complex YAML structures are loaded correctly."""
        schema = {
            "name": "complex_tool",
            "description": "A tool with complex structure",
            "parameters": {
                "type": "object",
                "properties": {
                    "required_param": {"type": "string", "description": "Required"},
                    "optional_param": {
                        "type": "integer",
                        "description": "Optional",
                        "default": 42,
                    },
                },
                "required": ["required_param"],
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(schema, f)
            temp_path = f.name

        try:
            result = load_tool_schema(temp_path)
            assert result == schema
        finally:
            Path(temp_path).unlink()

    def test_handles_complex_json_structure(self) -> None:
        """Test that complex JSON structures are loaded correctly."""
        schema = {
            "name": "complex_tool",
            "description": "A tool with complex structure",
            "parameters": {
                "type": "object",
                "properties": {
                    "required_param": {"type": "string", "description": "Required"},
                    "optional_param": {
                        "type": "integer",
                        "description": "Optional",
                        "default": 42,
                    },
                },
                "required": ["required_param"],
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(schema, f)
            temp_path = f.name

        try:
            result = load_tool_schema(temp_path)
            assert result == schema
        finally:
            Path(temp_path).unlink()

    def test_file_not_found_error_includes_path(self) -> None:
        """Test that FileNotFoundError includes the path in the message."""
        nonexistent_path = "/some/nonexistent/path/schema.yaml"
        with pytest.raises(FileNotFoundError) as exc_info:
            load_tool_schema(nonexistent_path)

        assert nonexistent_path in str(exc_info.value)

    def test_value_error_includes_path(self) -> None:
        """Test that ValueError includes the path in the message."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("invalid: [yaml")
            temp_path = f.name

        try:
            with pytest.raises(ValueError) as exc_info:
                load_tool_schema(temp_path)

            assert temp_path in str(exc_info.value)
        finally:
            Path(temp_path).unlink()
