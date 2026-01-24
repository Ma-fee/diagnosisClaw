"""
Migration script to convert existing agent and flow YAML configs into a unified agentpool_config.yaml.

This script reads:
- All agent definitions from packages/xeno-agent/config/agents/
- All flow definitions from packages/xeno-agent/config/flows/

And produces:
- A unified agentpool_config.yaml with agents and flows sections
"""

from pathlib import Path
from typing import Any

import yaml


def load_yaml_file(file_path: Path) -> dict[str, Any]:
    """Load a YAML file and return its contents."""
    return yaml.safe_load(file_path.read_text(encoding="utf-8")) or {}


def migrate_agents(agents_dir: Path) -> dict[str, dict[str, Any]]:
    """
    Load all agent YAML files and extract relevant fields.

    Args:
        agents_dir: Directory containing agent YAML files

    Returns:
        Dictionary mapping agent identifiers to agent configurations
    """
    agents = {}

    for agent_file in sorted(agents_dir.glob("*.yaml")):
        agent_data = load_yaml_file(agent_file)

        identifier = agent_data.get("identifier")
        if not identifier:
            print(f"Warning: No identifier found in {agent_file}, skipping")
            continue

        # Extract relevant fields
        agent_config = {
            "identifier": identifier,
            "name": agent_data.get("name", identifier),
            "role": agent_data.get("role", ""),
            "goal": agent_data.get("goal", ""),
            "backstory": agent_data.get("backstory", ""),
            "tools": agent_data.get("tools", []),
        }

        # Add optional skills if present
        if "skills" in agent_data:
            agent_config["skills"] = agent_data["skills"]

        # Add optional capabilities if present
        if "capabilities" in agent_data:
            agent_config["capabilities"] = agent_data["capabilities"]

        agents[identifier] = agent_config
        print(f"Loaded agent: {identifier}")

    return agents


def migrate_flows(flows_dir: Path) -> dict[str, dict[str, Any]]:
    """
    Load all flow YAML files and extract relevant fields.

    Args:
        flows_dir: Directory containing flow YAML files

    Returns:
        Dictionary mapping flow names to flow configurations
    """
    flows = {}

    for flow_file in sorted(flows_dir.glob("*.yaml")):
        flow_data = load_yaml_file(flow_file)

        flow_name = flow_data.get("name")
        if not flow_name:
            print(f"Warning: No name found in {flow_file}, skipping")
            continue

        # Extract participants as a dict for easier lookup
        participants = {}
        for participant in flow_data.get("participants", []):
            agent_id = participant.get("id")
            role = participant.get("role", "")
            if agent_id:
                participants[agent_id] = role

        # Extract delegation rules
        rules = [
            {
                "from": rule.get("from_agent"),
                "to": rule.get("to_agent"),
                "condition": rule.get("condition", ""),
            }
            for rule in flow_data.get("delegation_rules", [])
        ]

        # Extract flow configuration
        flow_config = {
            "name": flow_name,
            "description": flow_data.get("description", ""),
            "participants": participants,
            "rules": rules,
        }

        # Add tools configuration if present
        if "tools" in flow_data:
            flow_config["tools"] = flow_data["tools"]

        flows[flow_name] = flow_config
        print(f"Loaded flow: {flow_name}")

    return flows


def generate_agentpool_config(agents_dir: Path, flows_dir: Path, output_path: Path) -> None:
    """
    Generate the unified agentpool_config.yaml file.

    Args:
        agents_dir: Directory containing agent YAML files
        flows_dir: Directory containing flow YAML files
        output_path: Path where to write the unified config
    """
    # Load agents and flows
    agents = migrate_agents(agents_dir)
    flows = migrate_flows(flows_dir)

    # Build unified config
    config = {
        "agents": agents,
        "flows": flows,
    }

    # Write output file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(yaml.dump(config, allow_unicode=True, default_flow_style=False, sort_keys=False), encoding="utf-8")

    print(f"\nGenerated {output_path}")
    print(f"  - {len(agents)} agents")
    print(f"  - {len(flows)} flows")


def main():
    """Main entry point."""
    # Determine paths
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    agents_dir = project_root / "config" / "agents"
    flows_dir = project_root / "config" / "flows"
    output_path = project_root / "config" / "agentpool_config.yaml"

    print("Migrating to agentpool config...")
    print(f"  Agents dir: {agents_dir}")
    print(f"  Flows dir: {flows_dir}")
    print(f"  Output: {output_path}")
    print()

    # Validate directories exist
    if not agents_dir.exists():
        print(f"Error: Agents directory not found: {agents_dir}")
        exit(1)

    if not flows_dir.exists():
        print(f"Error: Flows directory not found: {flows_dir}")
        exit(1)

    # Generate config
    generate_agentpool_config(agents_dir, flows_dir, output_path)

    print("\nMigration complete!")


if __name__ == "__main__":
    main()
