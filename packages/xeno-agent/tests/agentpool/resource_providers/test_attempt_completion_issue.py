"""Test for attempt_completion result capture in new_task."""

import asyncio

from agentpool.agents.events import (
    StreamCompleteEvent,
    ToolCallCompleteEvent,
    ToolCallStartEvent,
)


async def test_attempt_completion_from_tool_call_start():
    """
    Test case 1: This shows the current bug - we're reading from raw_input
    which only contains input parameters, not the tool's return value.
    """
    print("\n=== Test Case 1: Current Bug (ToolCallStartEvent) ===")

    # Simulate attempt_completion being called
    tool_start_event = ToolCallStartEvent(
        tool_call_id="test-1",
        tool_name="attempt_completion",
        title="Complete task",
    )
    tool_start_event.raw_input = {"result": "this is input parameter"}

    # Current implementation (BUGGY):
    # We read from raw_input, which is just the input parameter
    args = tool_start_event.raw_input
    result_from_start = str(args.get("result", ""))

    print(f"ToolCallStartEvent.raw_input: {tool_start_event.raw_input}")
    print(f"Result captured from ToolCallStartEvent: {result_from_start}")
    print("Issue: This is the INPUT parameter, not the tool's RETURN value!")

    return result_from_start


async def test_attempt_completion_from_tool_call_complete():
    """
    Test case 2: This shows the correct approach - we should read from tool_result
    which contains the actual return value from the tool.
    """
    print("\n=== Test Case 2: Correct Approach (ToolCallCompleteEvent) ===")

    # Simulate attempt_completion being called and completed
    tool_complete_event = ToolCallCompleteEvent(
        tool_name="attempt_completion",
        tool_call_id="test-2",
        tool_input={"result": "input parameter"},
        tool_result="this is the actual return value",
        agent_name="test_agent",
        message_id="msg-1",
    )

    # Correct implementation:
    # We read from tool_result, which is the actual return value
    result_from_complete = str(tool_complete_event.tool_result)

    print(f"ToolCallCompleteEvent.tool_input: {tool_complete_event.tool_input}")
    print(f"ToolCallCompleteEvent.tool_result: {tool_complete_event.tool_result}")
    print(f"Result captured from ToolCallCompleteEvent: {result_from_complete}")
    print("Correct: This is the tool's RETURN value!")

    return result_from_complete


async def test_event_sequence():
    """
    Test case 3: Shows how to capture result correctly from ToolCallCompleteEvent.
    """
    print("\n=== Test Case 3: Event Sequence ===")

    # Create mock message for StreamCompleteEvent
    # Note: Import inside function due to sys.path requirement for agentpool module
    from agentpool.agents.message import Message  # noqa: PLC0415

    tool_start = ToolCallStartEvent(
        tool_call_id="test-3",
        tool_name="attempt_completion",
        title="Complete task",
    )
    tool_start.raw_input = {"result": "input"}

    tool_complete = ToolCallCompleteEvent(
        tool_name="attempt_completion",
        tool_call_id="test-3",
        tool_input={"result": "input"},
        tool_result="actual result",
        agent_name="test_agent",
        message_id="msg-1",
    )

    stream_complete = StreamCompleteEvent(message=Message(role="assistant", content="done"))

    events = [tool_start, tool_complete, stream_complete]

    print(f"Total events: {len(events)}")
    for i, event in enumerate(events):
        print(f"  Event {i}: {type(event).__name__}")
        if isinstance(event, ToolCallCompleteEvent):
            print(f"    tool_result: {event.tool_result}")

    # Show what happens with current implementation
    final_result = ""
    for event in events:
        if isinstance(event, ToolCallStartEvent) and event.tool_name == "attempt_completion":
            final_result = str(event.raw_input.get("result", ""))
            print(f"\nCurrent implementation captures: '{final_result}'")
            print("  (from ToolCallStartEvent.raw_input - WRONG!)")
            break

    # Show what should happen
    final_result = ""
    for event in events:
        if isinstance(event, ToolCallCompleteEvent) and event.tool_name == "attempt_completion":
            final_result = str(event.tool_result)
            print(f"\nCorrect implementation captures: '{final_result}'")
            print("  (from ToolCallCompleteEvent.tool_result - CORRECT!)")
            break


async def main():
    """Run all test cases."""
    print("=" * 60)
    print("Testing attempt_completion result capture issue")
    print("=" * 60)

    await test_attempt_completion_from_tool_call_start()
    await test_attempt_completion_from_tool_call_complete()
    await test_event_sequence()

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print("The current delegation_provider.py listens to ToolCallStartEvent")
    print("and reads from raw_input, which is the INPUT parameter.")
    print("")
    print("It should listen to ToolCallCompleteEvent instead and read from")
    print("tool_result, which is the actual RETURN value from the tool.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
