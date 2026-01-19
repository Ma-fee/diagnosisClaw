# Agent Gym Core System Architecture

## 1. System Overview
**Agent Gym** is a Multi-Agent Fault Diagnosis System based on **Self-Play (RL)** architecture. It simulates realistic diagnostic scenarios where a "User Agent" (simulating a customer with a specific equipment fault) interacts with a "Diagnostic Team" to resolve issues.

The system employs a **Decentralized Routing** mechanism, meaning there is no central controller. Instead, agents autonomously decide to handle tasks, delegate them, or hand off control to other specialists using specific tools.

## 2. Core Roles (Diagnostic Team)
The system is composed of four specialized roles, defined in `@packages/xeno-agent/docs/roles`:

### 🤖 Q&A Assistant (问答助手)
- **Type**: **Entry Point / Front Desk**
- **Responsibility**: 
  - Handles initial user interaction.
  - Answers simple queries (parameters, principles).
  - Assesses task difficulty.
  - Routes complex tasks to experts.
- **Key Capability**: **Handoff Only**. It cannot delegate subtasks, only switch control.
- **Tools**: `switch_mode`, `attempt_completion`, `ask_followup_question`.

### 🧠 Fault Expert (故障专家)
- **Type**: **Core Brain**
- **Responsibility**:
  - Leads the diagnostic process.
  - Formulates diagnostic plans and hypotheses.
  - Generates fault case reports.
  - Coordinates other agents.
- **Key Capability**: **Full Authority**. Can both **delegate** (new_task) and **handoff** (switch_mode).
- **Tools**: `new_task`, `switch_mode`, `attempt_completion`, `update_todo_list`.

### 🔧 Equipment Expert (设备专家)
- **Type**: **Hybrid Role (Worker + Active)**
- **Responsibility**:
  - **As Worker**: Analyzes images (VLM) or provides SOPs when requested.
  - **As Active Agent**: Guides users step-by-step through disassembly/testing operations.
- **Key Capability**:
  - Accepts tasks via `new_task` (returns result to caller).
  - Takes control via `switch_mode` (interacts with user directly).
- **Tools**: `search_database`, `attempt_completion`, `update_todo_list`.

### 📚 Material Assistant (资料助手)
- **Type**: **Worker Role**
- **Responsibility**:
  - Performs deep research (DeepResearch).
  - Retrieves technical documentation, industry standards, and cases.
- **Key Capability**: **Delegation Only**. Does not interact with users directly.
- **Tools**: `search_database`, `attempt_completion`.

---

## 3. Collaboration Mechanisms (Meta Tools)

Agents collaborate using three core "Meta Tools":

### 🔄 `switch_mode` (Handoff)
- **Semantics**: **"I'm handing this over to you."**
- **Behavior**: Transfers full control of the conversation to another agent. The current agent exits, and the target agent takes over the context.
- **Typical Use**: QA Agent hands off a complex P0300 error to the Fault Expert.

### 📨 `new_task` (Delegation)
- **Semantics**: **"Do this for me and report back."**
- **Behavior**: The caller (e.g., Fault Expert) pauses. The target agent (e.g., Search Agent) executes the specific task and returns a structured result. The caller then resumes.
- **Typical Use**: Fault Expert asks Search Agent to "Find the resistance value for model X".

### ✅ `attempt_completion` (Termination)
- **Semantics**: **"Task finished."**
- **Behavior**: Marks the diagnostic session as complete and submits the final report or solution.

---

## 4. Shared Capabilities
All agents are equipped with a standardized set of capabilities (Skills) to ensure consistency:

- **SEARCH_CAPBILITY**: Protocols for multi-source information retrieval.
- **CITATION_RULE**: Rules for verifying and citing sources.
- **IMAGE_RULES**: Guidelines for handling and analyzing images.
- **MARKDOWN_RULES**: Formatting standards for output.
- **LAYOUT_RULES**: Structured response templates.

---

## 5. Workflow Example
1. **User** enters with a fault description.
2. **QA Assistant** analyzes it. If complex, uses `switch_mode` -> **Fault Expert**.
3. **Fault Expert** analyzes the case.
   - Needs manual? Uses `new_task` -> **Material Assistant**.
   - Needs image analysis? Uses `new_task` -> **Equipment Expert**.
4. **Fault Expert** formulates a plan.
5. If physical repair is needed, uses `switch_mode` -> **Equipment Expert** for step-by-step guidance.
6. **Equipment Expert** completes the guide and uses `attempt_completion`.
