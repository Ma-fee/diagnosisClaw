# RFC 001: Core Agent System Architecture

## Metadata
- **Status**: Draft
- **Date**: 2026-01-18
- **Author**: Sisyphus
- **Scope**: System Architecture & Core Mechanisms

## 1. Context
We are building a specialized agent system for **engineering machinery fault diagnosis**. The system adopts a **Role-Playing Agent Architecture**, designed to handle complex diagnostic scenarios through a collaboration of specialized experts.

This RFC defines the core architecture, role responsibilities, and collaboration mechanisms that will serve as the foundation for the `xeno-agent` implementation.

## 2. Architecture Overview

### 2.1 Design Philosophy
- **Role-Play Based**: The system simulates a team of human experts.
- **Decentralized Routing**: There is no central "Super Orchestrator". Control flow is managed dynamically by agents using Handoff (`switch_mode`) and Delegation (`new_task`) mechanisms.
- **Stateful Context**: Context is preserved and passed during transitions to maintain conversation continuity.

### 2.2 Core Mechanisms

The system relies on three fundamental "Meta Tools" to manage agent interaction:

#### 🔄 Handoff ([`switch_mode`](../../../builtin_tools/switch_mode.yaml))
- **Definition**: Transferring full conversation control to another agent.
- **Behavior**: The current agent relinquishes control. The target agent receives the full conversation history and takes over as the primary interlocutor with the user.
- **Use Case**: QA Assistant realizing the problem is too complex and handing off to the Fault Expert.

#### 📨 Delegation ([`new_task`](../../../builtin_tools/new_task.yaml))
- **Definition**: Assigning a specific sub-task to a worker agent.
- **Behavior**: The primary agent remains in control but "blocks" to wait for the worker. The worker agent (e.g., Search Agent) executes the task and returns a structured result. The primary agent resumes execution.
- **Use Case**: Fault Expert delegating a "manual lookup" task to the Material Assistant.

#### ✅ Completion ([`attempt_completion`](../../../builtin_tools/attempt_completion.yaml))
- **Definition**: Signaling the end of a task or diagnosis.
- **Behavior**: Submits the final result/solution to the system/user and closes the current session.

---

## 3. Role Definitions

The system consists of four specialized roles. Detailed prompts and behaviors are defined in [`docs/roles/`](../../../roles/).

### 3.1 🤖 Q&A Assistant ([`问答助手.yaml`](../../../roles/问答助手.yaml))
- **Role Type**: **Gateway / Front Desk**
- **Responsibilities**:
  - User intent recognition.
  - Handling simple queries (parameters, basic principles).
  - Routing complex issues to experts.
- **Routing Logic**:
  - Simple Question -> Answer directly -> `attempt_completion`
  - Complex Fault -> `switch_mode(target="FaultExpert")`
  - Operation Guide -> `switch_mode(target="EquipmentExpert")`
- **Tools Used**: [`ask_followup_question`](../../../builtin_tools/ask_followup_question.yaml), [`attempt_completion`](../../../builtin_tools/attempt_completion.yaml), [`switch_mode`](../../../builtin_tools/switch_mode.yaml)

### 3.2 🧠 Fault Expert ([`故障专家.yaml`](../../../roles/故障专家.yaml))
- **Role Type**: **Orchestrator / Diagnostician**
- **Responsibilities**:
  - Phenomenon clarification & hypothesis generation.
  - Diagnostic planning.
  - Coordinating other agents for support.
- **Collaboration**:
  - Needs info? -> `new_task(target="MaterialAssistant")`
  - Needs diagram analysis? -> `new_task(target="EquipmentExpert")`
  - Needs physical execution? -> `switch_mode(target="EquipmentExpert")`
- **Tools Used**: [`ask_followup_question`](../../../builtin_tools/ask_followup_question.yaml), [`attempt_completion`](../../../builtin_tools/attempt_completion.yaml), [`update_todo_list`](../../../builtin_tools/update_todo_list.yaml), [`new_task`](../../../builtin_tools/new_task.yaml)

### 3.3 🔧 Equipment Expert ([`设备专家.yaml`](../../../roles/设备专家.yaml))
- **Role Type**: **Hybrid (Worker + Active)**
- **Responsibilities**:
  - **As Worker**: Analyzes device images, panels, or provides SOP content.
  - **As Active**: Guides users step-by-step through disassembly, testing, or repair.
- **Collaboration**:
  - Can be invoked via `new_task` for analysis.
  - Can be switched to via `switch_mode` for interactive guidance.
- **Tools Used**: [`ask_followup_question`](../../../builtin_tools/ask_followup_question.yaml), [`attempt_completion`](../../../builtin_tools/attempt_completion.yaml), [`update_todo_list`](../../../builtin_tools/update_todo_list.yaml)

### 3.4 📚 Material Assistant ([`资料助手.yaml`](../../../roles/资料助手.yaml))
- **Role Type**: **Worker / Researcher**
- **Responsibilities**:
  - Deep retrieval of technical manuals, historical cases, and industry standards.
  - Summarizing complex documents.
- **Collaboration**:
  - Invoked exclusively via `new_task`. Does not interact directly with the user.
- **Tools Used**: [`attempt_completion`](../../../builtin_tools/attempt_completion.yaml), `search_database`

---

## 4. Shared Capabilities

To ensure consistent behavior, all agents inherit a set of core capabilities defined in [`docs/capability/`](../../../capability/):

- **Markdown Protocol** ([`markdown.mdc`](../../../capability/markdown.mdc)): Standardized output formatting with strict citation rules.
- **Mermaid Generation** ([`mermaid.mdc`](../../../capability/mermaid.mdc)): Diagram generation for fault trees and workflows.
- **Search Capability** ([`search.mdc`](../../../capability/search.mdc)): Unified interface for knowledge base access.
- **Citation Rules** ([`citation.mdc`](../../../capability/citation.mdc)): Strict requirements for referencing sources (manuals/docs).
- **Image Handling** ([`image.mdc`](../../../capability/image.mdc)): Standardized protocol for receiving and analyzing user uploads.
- **Layout Requirements** ([`layout.mdc`](../../../capability/layout.mdc)): Mobile-first output formatting.

## 5. System Implementation Details

### 5.1 State Management

**Current Approach**: Session-Level Message Context

The system does not maintain a separate state management layer. Instead, all state is preserved through the conversation messages:

- **Session Continuity**: The entire conversation history (messages array) is passed between agents during `switch_mode` and `new_task` transitions
- **No External State Store**: All context resides in the LLM's message history
- **Self-Contained State**: Agents rely on the message history to understand previous decisions, tool calls, and intermediate results

**Implications**:
- State is implicitly managed by the LLM through its context window
- No need for separate state serialization/deserialization logic
- Simpler architecture with reduced complexity
- State durability is tied to session storage (handled by the orchestration layer)

### 5.2 Meta-Tools Interface

Meta-Tools are fully defined in [`docs/builtin_tools/`](../../../builtin_tools/). Each tool specification includes:

- **Name and Description**: Tool identifier and usage documentation
- **Parameters**: Complete parameter schema with types and validation rules
- **Expected Behavior**: Detailed execution semantics

Available Meta-Tools:
- [`switch_mode`](../../../builtin_tools/switch_mode.yaml): Handoff control to another agent
- [`new_task`](../../../builtin_tools/new_task.yaml): Delegate sub-task to worker agent
- [`attempt_completion`](../../../builtin_tools/attempt_completion.yaml): Signal task completion
- [`ask_followup_question`](../../../builtin_tools/ask_followup_question.yaml): Interactive user feedback
- [`update_todo_list`](../../../builtin_tools/update_todo_list.yaml): Task tracking and progress management

### 5.3 Error Handling

**Self-Healing Mechanism**: Error Feedback to LLM

When an agent encounters an error (tool failure, timeout, invalid operation), the system does not implement automatic retries. Instead:

1. **Error Injection**: The error message is injected into the conversation messages as a system or tool message
2. **LLM Self-Recovery**: The LLM receives the error context and determines the appropriate recovery strategy:
    - Retry with corrected parameters
    - Switch to a different approach
    - Handoff to another agent
    - Ask the user for clarification
3. **Flexible Response**: The LLM's reasoning capabilities allow it to adapt to various error scenarios without rigid error handling logic

**Examples**:
- Tool timeout → LLM may retry or use alternative tool
- Invalid parameter → LLM corrects parameter and re-invokes
- Network failure → LLM may switch to offline approach or inform user

### 5.4 Tool Implementation Details

This section details the specific message formatting and behavior for critical meta-tools during runtime.

#### 5.4.1 `new_task` - Subagent Message Formatting

When a parent agent invokes `new_task`, the subagent receives its first message with `role=user` formatted as:

```xml
<task>
{{message}}
</task>
After the task is completed, return the final result containing the following content using the attempt_completion tool.
<expected_output>
{{expected_output}}
</expected_output>
```

This ensures the subagent:
- Clearly understands the assigned task
- Knows the expected output format
- Is instructed to use `attempt_completion` to return results

#### 5.4.2 `attempt_completion` - Parent Agent Result Propagation

When a subagent calls `attempt_completion`, the result is returned to the parent agent as a `role=tool` message:

```
{{attempt_completion.result}}
```

The parent agent receives:
- The direct output from the subagent
- No wrapping or additional metadata
- Can immediately integrate the result into its reasoning

#### 5.4.3 `update_todo_list` - Todo State Management

**Backend Storage**:
- The system maintains a dictionary variable storing all todo items
- Each todo has: position (Pos), content, and status (notStarted | inProgress | completed)
- Incremental updates modify existing dictionary entries

**Markdown Generation**:
- Every call to `update_todo_list` generates a fresh markdown table
- Format: `| Pos | Content | Status |`
- Returned to agent as `role=tool` message

**Default Todo List Message**:
When no todo list has been created yet, `ACTIVE_TODO_LIST_MARKDOWN` displays:

```
You have not created a todo list yet. Create one with `update_todo_list` if your task is complicated or involves multiple steps.
```

This encourages agents to use todo tracking for complex multi-step tasks without forcing it for simple queries.

**User Message Template Injection**:
Every user message includes the current todo list via template injection:

```markdown
<user_message>
{{USER_INPUT}}

{{image_url}}
</user_message>

<environment_details>
# Current Mode
<slug>{{MODE}}</slug>

<current_date>{{DATE}}</current_date>

====

{{ACTIVE_TODO_LIST_MARKDOWN}}

====

Please think carefully before answering, as quality of your response is of highest priority. You have unlimited thinking tokens for this.
</environment_details>
```

**Key Behaviors**:
- Todo list visibility: Agents always see current progress in every user message
- State persistence: Todo state maintained across mode switches
- Progress tracking: LLM can plan and track multi-step workflows
- Date awareness: Current date provided for time-sensitive tasks
- Mode awareness: Current role slug available for context-aware responses

---

## 6. Implementation Roadmap
1. **Core Framework**: Implement the `Agent` base class and the Dispatcher logic for `switch_mode` and `new_task`.
2. **Tool Registry**: Implement the meta-tools and bind them to respective agents.
3. **Role Integration**: Port prompt definitions from `docs/roles` into the codebase.
4. **Message Context Management**: Ensure session-level messages are correctly passed during agent transitions.
