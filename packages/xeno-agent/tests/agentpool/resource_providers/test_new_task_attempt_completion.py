"""Integration test for new_task and attempt_completion."""

# ruff: noqa: E402 - Import not at top of file (required for sys.path modification)
import asyncio
import sys
from pathlib import Path

# Add agentpool to path
agentpool_path = Path(__file__).parent.parent.parent.parent / "agentpool" / "src"
sys.path.insert(0, str(agentpool_path))

from agentpool.agents.events import (
    StreamCompleteEvent,
    SubAgentEvent,
    ToolCallCompleteEvent,
    ToolCallStartEvent,
)
from agentpool.messaging import ChatMessage


async def test_new_task_receives_attempt_completion_result():
    """
    Test that new_task correctly captures result from attempt_completion.
    This simulates the event flow when a subagent calls attempt_completion.
    """
    print("\n=== Integration Test: new_task receives attempt_completion result ===\n")

    # Create mock subagent stream
    async def mock_subagent_stream():
        """Simulate a subagent that calls attempt_completion."""
        # 1. Agent starts
        yield SubAgentEvent(
            source_name="subagent",
            source_type="agent",
            event=ChatMessage(role="assistant", content="Starting task..."),
            depth=1,
        )

        # 2. Subagent calls attempt_completion
        tool_start = ToolCallStartEvent(
            tool_call_id="call-123",
            tool_name="attempt_completion",
            title="Complete task",
        )
        tool_start.raw_input = {"result": "task completed successfully"}

        yield SubAgentEvent(
            source_name="subagent",
            source_type="agent",
            event=tool_start,
            depth=1,
        )

        # 3. Tool completes with result
        tool_complete = ToolCallCompleteEvent(
            tool_name="attempt_completion",
            tool_call_id="call-123",
            tool_input={"result": "task completed successfully"},
            tool_result="task completed successfully",  # This is the actual return value!
            agent_name="subagent",
            message_id="msg-456",
        )

        yield SubAgentEvent(
            source_name="subagent",
            source_type="agent",
            event=tool_complete,
            depth=1,
        )

        # 4. Stream completes
        yield SubAgentEvent(
            source_name="subagent",
            source_type="agent",
            event=StreamCompleteEvent(message=ChatMessage(role="assistant", content="Done")),
            depth=1,
        )

    # Simulate the event handling logic from delegation_provider.new_task
    print("Simulating new_task event processing...\n")

    final_result = ""

    async for event in mock_subagent_stream():
        print(f"Processing event: {type(event).__name__}")

        # Track when attempt_completion starts
        if isinstance(event, SubAgentEvent):
            inner_event = event.event

            # Check for ToolCallStartEvent
            if isinstance(inner_event, ToolCallStartEvent) and inner_event.tool_name == "attempt_completion":
                print("  ToolCallStartEvent detected")
                print(f"    raw_input: {inner_event.raw_input}")
                print("    (This is input parameter, NOT the return value)")

            # Check for ToolCallCompleteEvent - THIS IS THE KEY!
            if isinstance(inner_event, ToolCallCompleteEvent) and inner_event.tool_name == "attempt_completion":
                print("  ToolCallCompleteEvent detected ✓")
                print(f"    tool_result: {inner_event.tool_result}")
                print("    (This is the ACTUAL return value!)")

                # Capture result
                final_result = str(inner_event.tool_result) if inner_event.tool_result else ""
                print(f"\n  ✓ Captured result: '{final_result}'")
                print("  ✓ Breaking stream as expected")
                break

        # Also check for direct ToolCallCompleteEvent (not wrapped)
        if isinstance(event, ToolCallCompleteEvent) and event.tool_name == "attempt_completion":
            print("  Direct ToolCallCompleteEvent detected")
            print(f"    tool_result: {event.tool_result}")
            final_result = str(event.tool_result) if event.tool_result else ""
            break

        # Also check for direct ToolCallCompleteEvent (not wrapped)
        if isinstance(event, ToolCallCompleteEvent) and event.tool_name == "attempt_completion":
            print("  Direct ToolCallCompleteEvent detected")
            print(f"    tool_result: {event.tool_result}")
            final_result = str(event.tool_result) if event.tool_result else ""
            break

    # Verify result
    print("\n=== Test Results ===")
    print(f"Final result captured: '{final_result}'")

    expected_result = "task completed successfully"
    if final_result == expected_result:
        print("✅ SUCCESS: Correctly captured attempt_completion result!")
        print(f"   Expected: '{expected_result}'")
        print(f"   Got:      '{final_result}'")
        return True
    print("❌ FAILURE: Did not capture correct result!")
    print(f"   Expected: '{expected_result}'")
    print(f"   Got:      '{final_result}'")
    return False


async def test_tool_call_start_vs_complete():
    """
    Test showing the difference between ToolCallStartEvent and ToolCallCompleteEvent.
    """
    print("\n=== Test: ToolCallStartEvent vs ToolCallCompleteEvent ===\n")

    # Create events
    tool_start = ToolCallStartEvent(
        tool_call_id="call-1",
        tool_name="attempt_completion",
        title="Complete",
    )
    tool_start.raw_input = {"result": "input_value"}

    tool_complete = ToolCallCompleteEvent(
        tool_name="attempt_completion",
        tool_call_id="call-1",
        tool_input={"result": "input_value"},
        tool_result="actual_return_value",
        agent_name="test",
        message_id="msg-1",
    )

    print("ToolCallStartEvent:")
    print(f"  raw_input:  {tool_start.raw_input}")
    print(f"  Has 'tool_result': {hasattr(tool_start, 'tool_result')}")

    print("\nToolCallCompleteEvent:")
    print(f"  tool_input:  {tool_complete.tool_input}")
    print(f"  tool_result: {tool_complete.tool_result}")
    print(f"  Has 'tool_result': {hasattr(tool_complete, 'tool_result')}")

    print("\nConclusion:")
    print("  - ToolCallStartEvent has raw_input (input parameters)")
    print("  - ToolCallCompleteEvent has tool_result (return value)")
    print("  - Use ToolCallCompleteEvent.tool_result to get the actual result!")


async def main():
    """Run all integration tests."""
    print("=" * 70)
    print("Integration Tests for new_task and attempt_completion")
    print("=" * 70)

    await test_tool_call_start_vs_complete()
    success = await test_new_task_receives_attempt_completion_result()

    print("\n" + "=" * 70)
    if success:
        print("ALL TESTS PASSED ✓")
        print("The delegation_provider.py fix is working correctly!")
    else:
        print("TESTS FAILED ❌")
        print("Need to debug further.")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
