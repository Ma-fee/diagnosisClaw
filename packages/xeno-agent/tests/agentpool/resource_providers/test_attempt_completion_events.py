"""Test to verify attempt_completion event structure in delegation."""

# ruff: noqa: E402 - Import not at top of file (required for sys.path modification)
import asyncio
import sys
from pathlib import Path

# Add agentpool to path
agentpool_path = Path(__file__).parent.parent.parent.parent / "agentpool" / "src"
sys.path.insert(0, str(agentpool_path))

from agentpool.agents.events import (
    SubAgentEvent,
    ToolCallCompleteEvent,
    ToolCallStartEvent,
)


async def test_tool_call_events():
    """Test the actual structure of tool call events."""
    print("\n=== Testing Tool Call Event Structures ===\n")

    # Test 1: ToolCallStartEvent
    print("1. ToolCallStartEvent:")
    tool_start = ToolCallStartEvent(
        tool_call_id="test-id-1",
        tool_name="attempt_completion",
        title="Complete task",
    )
    tool_start.raw_input = {"result": "input value"}

    print(f"   - tool_call_id: {tool_start.tool_call_id}")
    print(f"   - tool_name: {tool_start.tool_name}")
    print(f"   - raw_input: {tool_start.raw_input}")
    print(f"   - Attributes: {dir(tool_start)}")
    print(f"   - Has raw_input: {hasattr(tool_start, 'raw_input')}")

    # Test 2: ToolCallCompleteEvent
    print("\n2. ToolCallCompleteEvent:")
    tool_complete = ToolCallCompleteEvent(
        tool_name="attempt_completion",
        tool_call_id="test-id-2",
        tool_input={"result": "input value"},
        tool_result="actual return value",
        agent_name="test_agent",
        message_id="msg-1",
    )

    print(f"   - tool_call_id: {tool_complete.tool_call_id}")
    print(f"   - tool_name: {tool_complete.tool_name}")
    print(f"   - tool_input: {tool_complete.tool_input}")
    print(f"   - tool_result: {tool_complete.tool_result}")
    print(f"   - agent_name: {tool_complete.agent_name}")
    print(f"   - message_id: {tool_complete.message_id}")
    print(f"   - Attributes: {[a for a in dir(tool_complete) if not a.startswith('_')]}")
    print(f"   - Has tool_result: {hasattr(tool_complete, 'tool_result')}")
    print(f"   - Has result: {hasattr(tool_complete, 'result')}")

    # Test 3: SubAgentEvent wrapping ToolCallStartEvent
    print("\n3. SubAgentEvent wrapping ToolCallStartEvent:")
    subagent_event_start = SubAgentEvent(
        source_name="subagent",
        source_type="agent",
        event=tool_start,
        depth=1,
    )

    print(f"   - source_name: {subagent_event_start.source_name}")
    print(f"   - source_type: {subagent_event_start.source_type}")
    print(f"   - event type: {type(subagent_event_start.event).__name__}")
    print(f"   - event.tool_name: {subagent_event_start.event.tool_name}")
    print(f"   - event.raw_input: {subagent_event_start.event.raw_input}")

    # Test 4: SubAgentEvent wrapping ToolCallCompleteEvent
    print("\n4. SubAgentEvent wrapping ToolCallCompleteEvent:")
    subagent_event_complete = SubAgentEvent(
        source_name="subagent",
        source_type="agent",
        event=tool_complete,
        depth=1,
    )

    print(f"   - source_name: {subagent_event_complete.source_name}")
    print(f"   - source_type: {subagent_event_complete.source_type}")
    print(f"   - event type: {type(subagent_event_complete.event).__name__}")
    print(f"   - event.tool_name: {subagent_event_complete.event.tool_name}")
    print(f"   - event.tool_result: {subagent_event_complete.event.tool_result}")

    # Test 5: Match patterns
    print("\n=== Testing Pattern Matching ===\n")

    events_to_test = [
        ("ToolCallStartEvent", tool_start),
        ("ToolCallCompleteEvent", tool_complete),
        ("SubAgentEvent (ToolCallStart)", subagent_event_start),
        ("SubAgentEvent (ToolCallComplete)", subagent_event_complete),
    ]

    for event_name, event in events_to_test:
        print(f"Testing: {event_name}")
        match event:
            case ToolCallStartEvent(tool_name="attempt_completion", raw_input=args):
                print(f"  ✓ Matched ToolCallStartEvent, result from raw_input: {args.get('result')}")
            case ToolCallCompleteEvent(tool_name="attempt_completion", tool_result=result):
                print(f"  ✓ Matched ToolCallCompleteEvent, result: {result}")
            case SubAgentEvent(event=inner):
                match inner:
                    case ToolCallStartEvent(tool_name="attempt_completion", raw_input=args):
                        print(f"  ✓ Matched SubAgentEvent.ToolCallStartEvent, result from raw_input: {args.get('result')}")
                    case ToolCallCompleteEvent(tool_name="attempt_completion", tool_result=result):
                        print(f"  ✓ Matched SubAgentEvent.ToolCallCompleteEvent, result: {result}")
                    case _:
                        print(f"  ✗ SubAgentEvent inner event not matched: {type(inner).__name__}")
            case _:
                print(f"  ✗ Event not matched: {type(event).__name__}")

    print("\n=== SUMMARY ===")
    print("For attempt_completion:")
    print("  - ToolCallStartEvent has 'raw_input' field (input parameters)")
    print("  - ToolCallCompleteEvent has 'tool_result' field (return value)")
    print("  - When wrapped in SubAgentEvent, access via .event attribute")
    print("\nFor delegation_provider.py:")
    print("  - Listen to both ToolCallStartEvent AND ToolCallCompleteEvent")
    print("  - In SubAgentEvent, match inner.event for tool events")
    print("  - Use tool_result for final value, not raw_input")


async def main():
    await test_tool_call_events()


if __name__ == "__main__":
    asyncio.run(main())
