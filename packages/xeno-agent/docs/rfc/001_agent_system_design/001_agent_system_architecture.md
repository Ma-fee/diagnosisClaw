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

#### 🔄 Handoff (`switch_mode`)
- **Definition**: Transferring full conversation control to another agent.
- **Behavior**: The current agent relinquishes control. The target agent receives the full conversation history and takes over as the primary interlocutor with the user.
- **Use Case**: QA Assistant realizing the problem is too complex and handing off to the Fault Expert.

#### 📨 Delegation (`new_task`)
- **Definition**: Assigning a specific sub-task to a worker agent.
- **Behavior**: The primary agent remains in control but "blocks" to wait for the worker. The worker agent (e.g., Search Agent) executes the task and returns a structured result. The primary agent resumes execution.
- **Use Case**: Fault Expert delegating a "manual lookup" task to the Material Assistant.

#### ✅ Completion (`attempt_completion`)
- **Definition**: Signaling the end of a task or diagnosis.
- **Behavior**: Submits the final result/solution to the system/user and closes the current session.

---

## 3. Role Definitions

The system consists of four specialized roles. Detailed prompts and behaviors are defined in `docs/roles`.

### 3.1 🤖 Q&A Assistant (问答助手)
- **Role Type**: **Gateway / Front Desk**
- **Responsibilities**:
  - User intent recognition.
  - Handling simple queries (parameters, basic principles).
  - Routing complex issues to experts.
- **Routing Logic**:
  - Simple Question -> Answer directly -> `attempt_completion`
  - Complex Fault -> `switch_mode(target="FaultExpert")`
  - Operation Guide -> `switch_mode(target="EquipmentExpert")`

### 3.2 🧠 Fault Expert (故障专家)
- **Role Type**: **Orchestrator / Diagnostician**
- **Responsibilities**:
  - Phenomenon clarification & hypothesis generation.
  - Diagnostic planning.
  - Coordinating other agents for support.
- **Collaboration**:
  - Needs info? -> `new_task(target="MaterialAssistant")`
  - Needs diagram analysis? -> `new_task(target="EquipmentExpert")`
  - Needs physical execution? -> `switch_mode(target="EquipmentExpert")`

### 3.3 🔧 Equipment Expert (设备专家)
- **Role Type**: **Hybrid (Worker + Active)**
- **Responsibilities**:
  - **As Worker**: Analyzes device images, panels, or provides SOP content.
  - **As Active**: Guides users step-by-step through disassembly, testing, or repair.
- **Collaboration**:
  - Can be invoked via `new_task` for analysis.
  - Can be switched to via `switch_mode` for interactive guidance.

### 3.4 📚 Material Assistant (资料助手)
- **Role Type**: **Worker / Researcher**
- **Responsibilities**:
  - Deep retrieval of technical manuals, historical cases, and industry standards.
  - Summarizing complex documents.
- **Collaboration**:
  - Invoked exclusively via `new_task`. Does not interact directly with the user.

---

## 4. Shared Capabilities

To ensure consistent behavior, all agents inherit a set of core capabilities:

- **Markdown Protocol**: Standardized output formatting.
- **Search Capability**: Unified interface for knowledge base access.
- **Citation Rules**: Strict requirements for referencing sources (manuals/docs).
- **Image Handling**: Standardized protocol for receiving and analyzing user uploads.

## 5. Implementation Roadmap
1. **Core Framework**: Implement the `Agent` base class and the Dispatcher logic for `switch_mode` and `new_task`.
2. **Tool Registry**: Implement the meta-tools and bind them to respective agents.
3. **Role Integration**: Port prompt definitions from `docs/roles` into the codebase.
4. **State Management**: Ensure shared context (memory) is correctly serialized/deserialized during transitions.
