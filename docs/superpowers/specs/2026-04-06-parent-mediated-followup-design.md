# Parent-Mediated Follow-Up Design

## Overview

This design adds a parent-mediated follow-up flow for diagnosis routing in `diag-agent-v5`.
The user continues to interact only with `technical_assistant`.
`fault_expert` remains an internal worker invoked through `new_task`.
When `fault_expert` lacks critical information, it does not ask the user directly.
Instead, it returns a structured `needs_user_input` result to `technical_assistant`, which then asks the user through the existing `ask_followup_question` tool and resumes the delegated diagnosis with the user's answer.

This design solves the current OpenCode limitation where delegated subagents can emit questions that the frontend cannot meaningfully route back into the worker session.

## Problem Statement

The current system mixes two incompatible interaction models:

1. `technical_assistant` is the only stable user-facing agent in the OpenCode session.
2. `fault_expert` is currently invoked as a delegated worker through `new_task`.
3. `fault_expert` is also allowed to use `ask_followup_question`.

This creates a broken interaction boundary.
When `fault_expert` asks a follow-up question, the backend emits a pending question event, but the conversational authority still belongs to `technical_assistant`.
The frontend can display the question, but the mental model and session ownership are wrong: the worker behaves like an active conversational agent even though it is only a delegated subtask.

The result is fragile UX, unclear orchestration semantics, and difficult debugging.

## Goals

- Keep `technical_assistant` as the only user-facing agent in the OpenCode flow.
- Allow `fault_expert` to request missing information without directly interacting with the user.
- Preserve the existing `ask_followup_question` UI flow and OpenCode question endpoints.
- Make the worker-to-parent contract explicit and machine-readable.
- Keep the design compatible with future worker agents such as `equipment_expert` and `material_assistant`.

## Non-Goals

- Do not implement true session handoff or active-agent switching.
- Do not expose delegated subagents as independently chat-capable OpenCode sessions.
- Do not redesign the OpenCode question transport.
- Do not introduce multi-question questionnaires in the first iteration.

## Alternatives Considered

### Option 1: Parent-mediated follow-up with explicit worker result

`fault_expert` returns a structured `needs_user_input` result to `technical_assistant`.
`technical_assistant` then asks the user and resumes the worker with the answer.

Pros:
- Clear ownership boundary.
- No frontend changes required.
- Easy to test and reason about.
- Reusable for any worker agent.

Cons:
- Requires changes to the `new_task` return contract.
- Requires prompt and configuration updates for the parent and worker agents.

### Option 2: Backend interception of worker `ask_followup_question`

Allow `fault_expert` to keep calling `ask_followup_question`, but translate that into a parent-visible question behind the scenes.

Pros:
- Smaller prompt changes.
- Preserves current worker behavior superficially.

Cons:
- Hides orchestration semantics in backend magic.
- Harder to debug.
- Tool semantics become misleading because a worker appears to ask the user directly, but actually cannot.

### Option 3: Prompt-only discipline

Instruct `fault_expert` not to ask the user directly and instead explain the need in plain text or via `attempt_completion`.

Pros:
- Minimal code changes.

Cons:
- Not reliable.
- Relies on model obedience for a control-flow rule.
- Produces ambiguous outputs and brittle orchestration.

### Recommendation

Adopt Option 1.
The control-flow boundary is architectural, not stylistic.
It should be enforced by tools and result contracts rather than prompt wording alone.

## Proposed Architecture

### High-level flow

1. User sends a message to `technical_assistant`.
2. `technical_assistant` decides that deep diagnosis is needed and calls `new_task(mode="fault_expert", ...)`.
3. `fault_expert` analyzes the problem.
4. If enough information is available, `fault_expert` finishes with `attempt_completion`.
5. If critical information is missing, `fault_expert` calls a new worker-only tool named `need_more_info`.
6. The delegation layer converts that worker event into a structured `new_task` return payload with `status="needs_user_input"`.
7. `technical_assistant` receives that payload and immediately calls `ask_followup_question`.
8. The user replies in the existing OpenCode question flow.
9. `technical_assistant` re-invokes `new_task(mode="fault_expert", ...)`, now including the user's answer and any provided resume context.
10. The loop continues until `fault_expert` completes successfully.

### Boundary rule

Only parent agents with direct user ownership may invoke user-interaction tools.
Worker agents may request user input only through parent-return contracts.

For the first iteration:

- `technical_assistant` is user-facing.
- `fault_expert` is worker-only in delegated mode.

## Tooling Changes

### New tool: `need_more_info`

Add a worker-only tool schema under `packages/xeno-agent/config/tools/need_more_info.yaml`.

Parameters:

- `question: string`
  A single focused user-facing question.
- `follow_up: string`
  Suggested structured answers using the same `<suggest>` format accepted by `ask_followup_question`.
- `resume_context: string`
  Short continuation instructions for the parent to include when re-dispatching the worker after the user responds.
- `missing_fields: array[string]` optional
  Structured labels for what information is missing.
- `reason: string` optional
  Internal explanation for why the information is needed. This may be used for logs, traces, or future UI hints.

Example payload:

```json
{
  "question": "能否确认 SY215C 的发动机型号？",
  "follow_up": "<suggest>不确定，按常见配置继续诊断</suggest><suggest>我查看铭牌后再告知</suggest>",
  "resume_context": "拿到发动机型号后，继续判断喷油与进气路径。",
  "missing_fields": ["engine_model"],
  "reason": "不同发动机配置对应不同的喷油与进气排查路径。"
}
```

### `new_task` return envelope

Extend the delegation provider so that `new_task` no longer returns only a raw string.
It returns a JSON string envelope with one of two statuses:

Completed:

```json
{
  "status": "completed",
  "result": "..."
}
```

Needs input:

```json
{
  "status": "needs_user_input",
  "question": "...",
  "follow_up": "...",
  "resume_context": "...",
  "missing_fields": ["..."],
  "reason": "..."
}
```

The envelope remains a string at the tool transport boundary to avoid broad changes in tool plumbing, but the content is structured JSON and must be parsed by the parent agent.

### Why not overload `attempt_completion`

`attempt_completion` is already semantically defined as the final answer output tool.
Using it to represent "I cannot continue without user input" would create ambiguous tool semantics and complicate tracing.
`need_more_info` keeps completion and suspension distinct.

## Provider Changes

### Delegation provider

Modify `XenoDelegationProvider.new_task` in `packages/xeno-agent/src/xeno_agent/agentpool/resource_providers/delegation_provider.py`.

Current behavior:

- Watches for `attempt_completion`.
- Captures a final string result.
- Returns a string to the parent.

New behavior:

- Continue watching for `attempt_completion`.
- Also watch for `need_more_info`.
- Capture exactly one terminal worker outcome:
  - `attempt_completion` -> `status=completed`
  - `need_more_info` -> `status=needs_user_input`
- Emit a consistent JSON envelope string as the tool result.
- Preserve existing subagent streaming events for observability.

If both terminal tools are called in one worker run, treat it as an orchestration error and fail the task.
If neither is called but the stream completes normally, preserve the current fallback behavior and wrap the final text as `status=completed`.

### New provider entry or delegation-provider extension

Implement `need_more_info` in one of two ways:

1. Add it to `XenoDelegationProvider` as another built-in meta-tool.
2. Add a dedicated provider similar to `QuestionForUserProvider`.

Recommendation:
Implement it inside `XenoDelegationProvider`.
It is part of the delegation contract, not a generic user-interaction capability.

## Agent Configuration Changes

Update `packages/xeno-agent/config/diag-agent-v5.yaml`.

### `technical_assistant`

Keep:

- `ask_followup_question`
- `new_task`

Behavioral prompt updates:

- When `new_task` returns `status=completed`, continue normal orchestration.
- When `new_task` returns `status=needs_user_input`, immediately call `ask_followup_question` using the returned `question` and `follow_up`.
- After the user replies, call `new_task` again with:
  - original diagnostic context
  - previous worker findings if relevant
  - the user answer
  - the returned `resume_context`

### `fault_expert`

Remove:

- `ask_followup_question`

Add:

- `need_more_info`

Keep:

- `new_task`
- `attempt_completion`

Behavioral prompt updates:

- Never ask the user directly.
- If information is missing and diagnosis cannot proceed safely, call `need_more_info`.
- Use `attempt_completion` only when the delegated diagnosis task is truly complete.

This establishes `fault_expert` as a true worker role in the internal-upgrade flow.

## Prompt Contract

### `technical_assistant` prompt requirements

The prompt must explicitly instruct the agent to parse the `new_task` result as structured JSON.

Required rules:

- `new_task` returns a JSON envelope, not plain prose.
- `status=completed` means the worker finished and returned a usable diagnosis result.
- `status=needs_user_input` means the worker is blocked pending additional information.
- In the blocked case, `technical_assistant` must ask the user via `ask_followup_question` and must not invent missing values.

### `fault_expert` prompt requirements

Required rules:

- `fault_expert` operates as a delegated specialist and never owns user interaction.
- If missing information is essential, call `need_more_info`.
- Keep `question` atomic and `follow_up` actionable.
- Include a short `resume_context` that helps the parent resume efficiently.

## Data Flow Example

### Initial diagnosis

User:

```text
SY215C 挖掘机冒黑烟，动力不足。
```

`technical_assistant` delegates:

```json
{
  "mode": "fault_expert",
  "message": "...黑烟+动力不足的背景...",
  "expected_output": "Return a JSON envelope string via completion or need_more_info."
}
```

### Worker blocks on missing info

`fault_expert` returns:

```json
{
  "status": "needs_user_input",
  "question": "能否确认发动机型号？",
  "follow_up": "<suggest>不确定，按常见配置继续诊断</suggest><suggest>我查看铭牌后再告知</suggest>",
  "resume_context": "收到发动机型号后，继续区分喷油系统与进气系统诊断路径。"
}
```

### Parent asks user

`technical_assistant` calls `ask_followup_question` with the returned question and options.

### User answers

User selects:

```text
不确定，按常见配置继续诊断
```

### Parent resumes worker

`technical_assistant` re-dispatches:

```markdown
Original issue: SY215C 挖掘机冒黑烟，动力不足。

Worker requested additional information:
- Engine model

User answer:
- 不确定，按常见配置继续诊断

Resume context:
- 收到发动机型号后，继续区分喷油系统与进气系统诊断路径。

Proceed using the best-effort common configuration path and state uncertainty explicitly.
```

## Error Handling

### Worker misuse

If a worker still emits direct user-facing tool calls after the configuration change, treat that as a prompt/configuration bug.
The first version does not need a hard runtime guard, but logs should make misuse obvious.

### Invalid worker envelope

If `technical_assistant` receives malformed JSON from `new_task`, it should treat that as a worker failure and either:

- retry once with clearer instructions, or
- return a safe fallback response to the user that the diagnosis flow encountered an internal routing issue.

The prompt should strongly bias the parent toward one retry before failing.

### Ambiguous termination

If the worker emits both `need_more_info` and `attempt_completion`, the provider should raise a `ToolError`.
The parent must receive a failure rather than a silently chosen branch.

## Testing Strategy

### Unit tests

Add unit coverage for the delegation provider:

- `need_more_info` result becomes a `status=needs_user_input` envelope.
- `attempt_completion` result becomes a `status=completed` envelope.
- conflicting terminal tool calls raise an error.
- stream completion without a terminal tool falls back to `status=completed`.

### Integration tests

Add an end-to-end test for the parent-mediated loop:

1. `technical_assistant` delegates to `fault_expert`
2. `fault_expert` returns `needs_user_input`
3. `technical_assistant` asks the user
4. user answer is injected
5. `technical_assistant` re-delegates
6. `fault_expert` completes successfully

### Regression expectations

Verify:

- OpenCode question endpoints remain unchanged.
- Only `technical_assistant` produces user-facing questions in this flow.
- Existing direct-completion delegation still works.

## Rollout Plan

1. Add `need_more_info` schema and tool implementation.
2. Extend delegation provider to emit structured `new_task` envelopes.
3. Update `diag-agent-v5.yaml` tool availability.
4. Update `technical_assistant` and `fault_expert` prompts.
5. Add unit and integration tests.
6. Validate the flow in OpenCode with a diagnostic scenario that requires one follow-up.

## Open Questions Resolved

### Why not use `question_for_user`?

The first iteration targets a single blocked-question loop.
`question_for_user` is more complex and is better reserved for future multi-field collection flows.
Using `ask_followup_question` keeps the initial change small and aligned with the current UI path.

### Why not let the frontend talk to the worker directly?

That would require active-agent switching or worker session exposure, which is a different architecture.
This design intentionally keeps the frontend unchanged and clarifies ownership at the orchestration layer.

## Acceptance Criteria

- `technical_assistant` remains the only user-facing agent in the OpenCode diagnostic flow.
- `fault_expert` can block for additional information without directly calling user-facing question tools.
- `new_task` returns a structured envelope that allows parent agents to distinguish completion from user-input suspension.
- A blocked diagnosis can resume after the user answers, without switching frontend session ownership.
- Existing completion-based delegated tasks continue to function.
