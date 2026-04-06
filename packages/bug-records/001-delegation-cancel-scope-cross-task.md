# BUG-001: RuntimeError: Attempted to exit cancel scope in a different task

## 基本信息

- **文件**: `packages/xeno-agent/src/xeno_agent/agentpool/resource_providers/delegation_provider.py`
- **发现时间**: 2026-03-31
- **严重程度**: 高（导致子 agent 委派时运行时崩溃）

## 错误信息

```
RuntimeError: Attempted to exit cancel scope in a different task than it was entered in
```

完整调用链：
```
agentpool/agents/native_agent/agent.py, line 712, in _stream_events
    yield combined
| GeneratorExit
...
RuntimeError: Attempted to exit cancel scope in a different task than it was entered in
```

## 根本原因

`new_task` 工具在迭代子 agent stream 时，一旦检测到 `attempt_completion` 或 `StreamCompleteEvent` 就执行 `break`。

`break` 触发 Python 对 async generator 调用 `aclose()`，向生成器内部抛入 `GeneratorExit`。`GeneratorExit` 传播到 `async with agentlet.iter()` 的 `__aexit__`，anyio 在此处尝试清理 cancel scope，但该 cancel scope 在子 agent 的 task 中创建，而清理发生在外层 task 中，因此报错。

触发路径：
```
break
  → stream.aclose()
    → GeneratorExit 注入 _stream_events 生成器
      → async with agentlet.iter().__aexit__ 被触发
        → anyio cancel scope 在错误的 task 中退出
          → RuntimeError
```

## 修改前的代码

```python
async for event in stream:
    match event:
        # Track when attempt_completion is called and stop subagent execution
        case ToolCallStartEvent(tool_name="attempt_completion", raw_input=args):
            # Capture the 'result' parameter from tool input
            final_result = str(args.get("result", ""))
            # Stop subagent from continuing execution
            break

        # Track when attempt_completion completes and capture final result
        case ToolCallCompleteEvent(tool_name="attempt_completion", tool_result=completion_result):
            # Capture the final result from the completed tool call
            final_result = str(completion_result) if completion_result else ""
            await ctx.events.emit_event(
                SubAgentEvent(
                    source_name=target_agent,
                    source_type=source_type,
                    event=StreamCompleteEvent(message=ChatMessage(content=final_result, role="assistant")),
                    child_session_id=child_session_id,
                ),
            )
            # Stop subagent from continuing execution
            break

        # Handle SubAgentEvent wrapping - preserve child_session_id for navigation
        case SubAgentEvent(
            source_name=source_name,
            source_type=source_type,
            event=inner_event,
            child_session_id=inner_child_session_id,
        ):
            nested_event = SubAgentEvent(
                source_name=source_name,
                source_type=source_type,
                event=inner_event,
                child_session_id=inner_child_session_id or child_session_id,
            )
            await ctx.events.emit_event(nested_event)

        # Capture final result from StreamCompleteEvent if attempt_completion wasn't used
        case StreamCompleteEvent(message=final_message):
            if final_message and final_message.content:
                final_result = str(final_message.content)
            await ctx.events.emit_event(
                SubAgentEvent(
                    source_name=target_agent,
                    source_type=source_type,
                    event=StreamCompleteEvent(message=ChatMessage(content=final_result, role="assistant")),
                    child_session_id=child_session_id,
                ),
            )
            # Stop subagent from continuing execution
            break

        # Wrap other events with session tracking (RFC-0015)
        case _:
            subagent_event = SubAgentEvent(
                source_name=target_agent,
                source_type=source_type,
                event=event,
                depth=current_depth + 1,
                child_session_id=child_session_id,
            )
            await ctx.events.emit_event(subagent_event)
# except (GeneratorExit, asyncio.CancelledError):
#     # Stream was cancelled by break statement, which is expected behavior
#     # when attempt_completion is detected. This prevents cleanup code from
#     # running in a different async task context.
#     pass
```

## 修改后的代码

```python
_completion_emitted = False
async for event in stream:
    match event:
        # Track when attempt_completion is called
        case ToolCallStartEvent(tool_name="attempt_completion", raw_input=args):
            # Capture the 'result' parameter from tool input
            final_result = str(args.get("result", ""))

        # Track when attempt_completion completes and capture final result
        case ToolCallCompleteEvent(tool_name="attempt_completion", tool_result=completion_result):
            # Capture the final result from the completed tool call
            final_result = str(completion_result) if completion_result else ""
            await ctx.events.emit_event(
                SubAgentEvent(
                    source_name=target_agent,
                    source_type=source_type,
                    event=StreamCompleteEvent(message=ChatMessage(content=final_result, role="assistant")),
                    child_session_id=child_session_id,
                ),
            )
            _completion_emitted = True

        # Handle SubAgentEvent wrapping - preserve child_session_id for navigation
        case SubAgentEvent(
            source_name=source_name,
            source_type=source_type,
            event=inner_event,
            child_session_id=inner_child_session_id,
        ):
            nested_event = SubAgentEvent(
                source_name=source_name,
                source_type=source_type,
                event=inner_event,
                child_session_id=inner_child_session_id or child_session_id,
            )
            await ctx.events.emit_event(nested_event)

        # Capture final result from StreamCompleteEvent if attempt_completion wasn't used
        case StreamCompleteEvent(message=final_message):
            if not _completion_emitted:
                if final_message and final_message.content:
                    final_result = str(final_message.content)
                await ctx.events.emit_event(
                    SubAgentEvent(
                        source_name=target_agent,
                        source_type=source_type,
                        event=StreamCompleteEvent(message=ChatMessage(content=final_result, role="assistant")),
                        child_session_id=child_session_id,
                    ),
                )

        # Wrap other events with session tracking (RFC-0015)
        case _:
            subagent_event = SubAgentEvent(
                source_name=target_agent,
                source_type=source_type,
                event=event,
                depth=current_depth + 1,
                child_session_id=child_session_id,
            )
            await ctx.events.emit_event(subagent_event)
```

## 修复方案说明

- **核心变更**：移除所有 `break` 语句，改用 `_completion_emitted` 标志位
- **原理**：让 async generator 自然耗尽（`StopAsyncIteration`），而非强制 `aclose()`，从而避免跨 task 触发 anyio cancel scope 清理
- **副作用**：子 agent 在 `attempt_completion` 返回后可能多一次 LLM 调用生成收尾文本，但不影响结果正确性
- **重复 StreamCompleteEvent 防护**：用 `_completion_emitted` 标志避免在已通过 `attempt_completion` 捕获结果后再次发送 `StreamCompleteEvent`
