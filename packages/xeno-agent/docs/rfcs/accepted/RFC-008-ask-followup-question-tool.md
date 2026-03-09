# RFC 008: Strict Schema AskFollowupQuestion Tool

## Metadata
- **Status**: Draft
- **Date**: 2026-01-29
- **Author**: Antigravity
- **Scope**: Tool Implementation & AgentPool Integration

## 1. Context
The `xeno-agent` system architecture (defined in `RFC-001`) relies on a strict `ask_followup_question` tool. This tool is critical for the "Gateway / Front Desk" role (Q&A Assistant) and others to interact with users in a structured way.

Currently, `agentpool` provides a generic `QuestionTool` (`agentpool.tool_impls.question.tool.QuestionTool`) which allows the LLM to generate any JSON schema for the response. While flexible, this differs from the strict `question` + `follow_up` (XML-tagged suggestions) signature required by `xeno-agent`'s prompts and existing behavior definitions.

## 2. Problem Statement
1.  **Schema Mismatch**: `xeno-agent` prompts expect a tool with `question` (str) and `follow_up` (str containing `<suggest>` tags). The existing `QuestionTool` expects a `prompt` and an optional `response_schema` dictionary.
2.  **Behavior Consistency**: We need to enforce the specific behavior of parsing `<suggest>` tags into structured options, ensuring the UI (OpenCode/ACP) renders them as buttons/choices, rather than relying on the LLM to correctly construct a JSON schema every time.
3.  **Compatibility**: The implementation must utilize `agentpool`'s underlying `handle_elicitation` mechanism to ensure compatibility with all clients (OpenCode, Zed, ACP, etc.).

## 3. Proposed Design

We will implement a new tool class `AskFollowupQuestionTool` within `xeno-agent` (or `agentpool` extensions) that bridges the strict input schema to the `agentpool` elicitation protocol.

### 3.1 Tool Interface
The tool will be defined with the following Pydantic model for arguments:

```python
class AskFollowupQuestionArgs(BaseModel):
    question: str = Field(..., description="A single, focused question...")
    follow_up: str = Field(..., description="A string containing 2-4 suggested answers wrapped in <suggest> tags...")
```

### 3.2 Implementation Logic

The tool will be implemented as a standalone asynchronous function to be compatible with `agentpool`'s `type: import` configuration.

**Function Signature**:
```python
async def ask_followup_question(
    ctx: AgentContext, 
    question: str, 
    follow_up: str
) -> ToolResult:
    ...
```

**Execution Flow**:
1.  **Receive Input**: Function called with `question` text and `follow_up` XML string.
2.  **Parse Options**: ... (same as before)
3.  **Construct Schema**: ... (same as before)
4.  **Delegate to Context**: Call `ctx.handle_elicitation(params)`.
5.  **Return Result**: ... (same as before)

### 3.3 Option Parsing Strategy
... (same as before)

### 3.4 Handling "Input" Type Options
... (same as before)

## 4. Compatibility & Integration
... (same as before)

## 5. Implementation Plan

1.  Create `packages/xeno-agent/src/xeno_agent/tools/ask_followup_question.py`.
2.  Implement `ask_followup_question` function with regex parsing.
3.  Unit test the function.

## 6. Configuration Usage

To use this tool in `agentpool` (e.g., `packages/xeno-agent/config/diag-agent.yaml`), replace the existing `type: question` configuration with `type: import`:

```yaml
.anchors:
  question_tool: &question_tool
    type: import
    import_path: xeno_agent.tools.ask_followup_question:ask_followup_question
    name: ask_followup_question
    description: |-
      The sole interactive tool for obtaining information from users.
      ... (Include full prompt description from RFC-001) ...
      
      ### **Usage Principles**
      ...
```

## 6. Open Questions
- **Multi-select**: `ask_followup_question.yaml` implies single choice for branching logic. Should we support multi-select if implied? *Decision: Default to single-select for now to match `switch_mode` branching logic.*
- **Rich Metadata**: How to pass `next_action`? *Decision: The agent handles the next action based on the string result. The tool doesn't need to auto-trigger the next action; the LLM will see the result and decide.*
