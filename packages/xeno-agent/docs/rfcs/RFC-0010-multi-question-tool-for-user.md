---
rfc_id: RFC-0010
title: Multi-Question Tool (question_for_user) for User Interactions
status: DRAFT
author: Xeno-Agent Team
reviewers:
created: 2026-03-11
last_updated: 2026-03-11
decision_date:
related_rfcs:
  - RFC-0008: Ask Followup Question Tool
references:
  - /packages/xeno-agent/docs/survey/opencode/question-tool-survey.md
  - /packages/agent-client-protocol/docs/rfds/elicitation.mdx
---

# RFC-0010: Multi-Question Tool (question_for_user) for User Interactions

## Overview

This RFC proposes a new tool `question_for_user` that enables agents to ask users multiple structured questions in a single interaction, supporting various question types (single choice, multiple choice, text input) through a unified XML-based format.

The design is inspired by OpenCode's Question Tool survey and aims to provide a consistent, extensible way to collect structured information from users across different frontend implementations (ACP, OpenCode, Zed Editor).

## Table of Contents

- [Background & Context](#background--context)
- [Problem Statement](#problem-statement)
- [Goals & Non-Goals](#goals--non-goals)
- [Evaluation Criteria](#evaluation-criteria)
- [Options Analysis](#options-analysis)
- [Recommendation](#recommendation)
- [Technical Design](#technical-design)
- [Implementation Plan](#implementation-plan)
- [Open Questions](#open-questions)
- [Decision Record](#decision-record)
- [References](#references)

---

## Background & Context

### Current State

Currently, agents use `ask_followup_question` (RFC-0008) to ask users questions. This tool works well for:
- Single questions with suggest options
- Simple text input prompts

However, it has limitations:
- Cannot easily ask multiple questions atomically
- Suggest-based question format is embedded in free text
- Limited type safety for different question types

### Historical Context

- **RFC-0008**: Introduced `ask_followup_question` with `<suggest>` tags for single questions
- **OpenCode Survey**: Documented OpenCode's native `question` tool capabilities
- **Need**: Agents frequently need to ask multiple related questions (e.g., collecting equipment model, symptom, and occurrence time together)

### Glossary

| Term | Definition |
|------|------------|
| Questionnaire | XML string containing one or more questions with their options |
| Question Type | The input type: `enum` (single choice), `multi` (multiple choice), `input` (free text) |
| Option Label | Short display text for choices (1-5 words) |
| Suggest Tag | XML element representing an answer option |

---

## Problem Statement

### The Problem

Current tooling forces agents to:
1. Ask questions one at a time, requiring multiple round-trips
2. Parse answers from free-form text
3. Handle different UIs with inconsistent formats

### Evidence

- Fault diagnosis agents need to collect: equipment type + model + symptoms → currently requires 3 separate tool calls
- Configuration agents need: format preference + detail level + language → fragmented user experience
- Previous attempts to use `ask_followup_question` for multi-question scenarios result in confusing UI rendering

### Impact of Inaction

- **User Experience**: Fragmented, slow interaction requiring multiple confirmations
- **Agent Efficiency**: Increased context window usage due to multiple messages
- **Code Complexity**: Agents need complex state management to track question sequences

---

## Goals & Non-Goals

### Goals (In Scope)

1. Enable single tool call to ask multiple structured questions
2. Support unified XML format for all question types (single, multi, input)
3. Provide type-safe answers indexed by question order
4. **Full compatibility with ACP Elicitation protocol** (form mode)
5. **OpenCode-compatible semantics** for agent prompts and responses
6. Clear separation from existing `ask_followup_question` (RFC-0008)

### Non-Goals (Out of Scope)

1. Dynamic question generation based on previous answers (conditional flows)
2. Complex validation rules (regex, range checking)
3. Support for non-text inputs (uploads, drawings)
4. Replacement of `ask_followup_question` (both tools coexist)

### Success Criteria

- [ ] Single XML field can represent 1+ questions with mixed types
- [ ] Answers returned as structured array matching question order
- [ ] Works with current ACP Server without frontend changes (using standard Elicit)
- [ ] Prompt documentation includes clear examples for LLM

---

## Evaluation Criteria

| Criterion | Weight | Description | Minimum Threshold |
|-----------|--------|-------------|-------------------|
| Format Consistency | High | Single XML format works for 1-N questions | Must not require different formats for single vs multi |
| Type Safety | High | Questions types validated at parse time | Invalid types must be detected before sending to user |
| Backward Compatibility | Medium | Existing tools continue to work | RFC-0008 tool unchanged |
| Implementation Complexity | Medium | Reasonable effort to implement and maintain | Single tool implementation, one provider file |
| Frontend Compatibility | High | Works with ACP/OpenCode/Zed without custom UI | Must use standard MCP ElicitForm |
| LLM Usability | High | XML format intuitive for LLM to generate | Clear examples in prompt |

---

## Options Analysis

### Option 1: Single XML Field (`questionnaire`)

**Description**

A single field `questionnaire` containing XML with `<question>` tags, supporting mixed types via `type` attribute.

```xml
<question header="Model" type="enum">
  <text>What is the equipment model?</text>
  <suggest>SY215C</suggest>
  <suggest>SY365H</suggest>
</question>
<question header="Symptoms" type="multi">
  <text>Select all that apply:</text>
  <suggest>Black smoke</suggest>
  <suggest>Power loss</suggest>
</question>
```

**Advantages**

- Unified format for single and multiple questions
- Self-documenting XML structure
- Easy to parse and validate
- Extensible: new types can be added as attributes
- Single field keeps API simple

**Disadvantages**

- Requires XML parsing (but standard library sufficient)
- LLM needs to learn XML structure (mitigated by good examples)
- Slightly more verbose than minimal format

**Evaluation Against Criteria**

| Criterion | Rating | Notes |
|-----------|--------|-------|
| Format Consistency | Excellent | Same format for any question count |
| Type Safety | Good | Type attribute clearly specified |
| Backward Compatibility | Good | New tool, no impact on existing |
| Implementation Complexity | Medium | XML parsing required |
| Frontend Compatibility | Good | Maps to standard Elicit schema |
| LLM Usability | Good | XML is familiar to modern LLMs |

**Effort Estimate**

- Complexity: Medium
- Resources: 1 developer, 2-3 days
- Dependencies: None (uses existing AgentPool infrastructure)

---

### Option 2: Structured JSON Parameter

**Description**

Use JSON array parameter with explicit structure:

```json
{
  "questions": [
    {
      "header": "Model",
      "type": "enum",
      "text": "What is the equipment model?",
      "options": ["SY215C", "SY365H"]
    }
  ]
}
```

**Advantages**

- Native JSON parsing
- Type safety through JSON Schema
- Direct mapping to most languages

**Disadvantages**

- Cannot leverage existing `<suggest>` rendering in ACP Server
- Would require custom UI components
- Less flexible for complex option descriptions
- Breaks consistency with RFC-0008's suggest approach

**Evaluation Against Criteria**

| Criterion | Rating | Notes |
|-----------|--------|-------|
| Format Consistency | Good | Consistent JSON structure |
| Type Safety | Excellent | JSON Schema validation |
| Backward Compatibility | Good | New tool |
| Implementation Complexity | High | Requires custom Elicit schema |
| Frontend Compatibility | Poor | Needs new UI components |
| LLM Usability | Excellent | JSON is very familiar |

---

### Option 3: Extend ask_followup_question (RFC-0008)

**Description**

Extend existing tool to support `<question>` tags within the `follow_up` field.

**Advantages**

- Reuses existing tool infrastructure
- No new provider needed

**Disadvantages**

- Mixes concerns: single vs multi question handling
- Complicates existing tool logic
- Risk of breaking existing behavior
- Less clear tool contract

**Evaluation Against Criteria**

| Criterion | Rating | Notes |
|-----------|--------|-------|
| Format Consistency | Poor | Different formats within same tool |
| Type Safety | Medium | Harder to validate mixed formats |
| Backward Compatibility | Risky | Changes to existing tool |
| Implementation Complexity | High | Complex branching logic |
| Frontend Compatibility | Good | Reuses existing |
| LLM Usability | Poor | Confusing when to use old vs new |

---

### Options Comparison Summary

| Criterion | Option 1: XML | Option 2: JSON | Option 3: Extend RFC-0008 |
|-----------|---------------|----------------|---------------------------|
| Format Consistency | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| Type Safety | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| Backward Compatibility | ⭐⭐⭐ | ⭐⭐⭐ | ⭐ |
| Implementation Complexity | ⭐⭐ | ⭐ | ⭐⭐ |
| Frontend Compatibility | ⭐⭐⭐ | ⭐ | ⭐⭐⭐ |
| LLM Usability | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| **Overall** | **Recommended** | | |

---

## Recommendation

### Recommended Option

**Option 1: Single XML Field (`questionnaire`)**

### Justification

1. **Format Consistency**: The XML approach provides a single, self-describing format that works for both single and multiple questions, eliminating the need for different handling paths.

2. **Frontend Compatibility**: By using XML with `<suggest>` tags (similar to RFC-0008), we can leverage existing ACP Server rendering capabilities without requiring custom UI components.

3. **Type Safety**: The `type` attribute provides clear, parseable question type information, enabling proper validation at parse time.

4. **Separation of Concerns**: Creating a new tool (`question_for_user`) keeps the existing `ask_followup_question` stable while providing a clear upgrade path for complex scenarios.

### Accepted Trade-offs

1. **XML Parsing Overhead**: Acceptable because Python's standard `xml.etree.ElementTree` is sufficient and performant for this use case.

2. **LLM Learning Curve**: Mitigated by comprehensive examples in the tool schema description and clear attribute naming.

### Conditions

- Tool must be marked as distinct from `ask_followup_question` in documentation
- XML schema must be strictly validated with clear error messages
- Fallback to text-based rendering if XML parsing fails

---

## Protocol Compatibility

### ACP Elicitation Protocol

This tool is designed to work with the **Agent-Client Protocol (ACP) Elicitation** mechanism as defined in `/packages/agent-client-protocol/docs/rfds/elicitation.mdx`.

#### Compatibility Matrix

| Feature | ACP Elicitation | Tool Support | Notes |
|---------|-----------------|--------------|-------|
| Form mode | `mode: "form"` | ✅ Supported | Primary mode |
| URL mode | `mode: "url"` | ❌ Not applicable | Out of scope |
| JSON Schema | Restricted subset | ✅ Full | Flat objects with primitives |
| Multi-select | Array enum | ✅ Supported | Via `type="multi"` |
| Single-select | String enum | ✅ Supported | Via `type="enum"` |
| Text input | String type | ✅ Supported | Via `type="input"` |
| Default values | `default` field | ⚠️ Optional | Can be added in future |

#### Type Mapping Reference

This table maps Tool XML types to ACP Elicitation schema and OpenCode equivalents:

| Tool Type/Attribute | XML Example | ACP Schema Type | ACP Properties | OpenCode Equivalent |
|---------------------|-------------|-----------------|----------------|---------------------|
| **enum** | `<question type="enum">` | `string` with `oneOf` | `const` + `title` for each option | `type: "enum"` + options |
| **multi** | `<question type="multi">` | `array` with enum `items` | `items.enum` + `uniqueItems: true` | `type: "array"` + `items.enum` |
| **input** | `<question type="input">` | `string` | `minLength`, `maxLength`, `pattern` | Direct string schema |
| **description** | `<suggest description="...">` | N/A (UI hint) | `x-option-descriptions` or `title` | `options[].description` |
| **string formatted** | *(future)* | `string` with `format` | `format: "email"\|"uri"\|"date"\|"date-time"` | Same |
| **number** | *(future)* | `number` or `integer` | `minimum`, `maximum` | Same |
| **boolean** | *(future)* | `boolean` | `default` | `type: "boolean"` |

#### Mapping Examples

**1. Single Select (`enum`)**

Tool XML:
```xml
<question header="Model" type="enum">
  <text>Select equipment model:</text>
  <suggest description="21.5 ton excavator, popular model">SY215C</suggest>
  <suggest description="36.5 ton heavy-duty excavator">SY365H</suggest>
  <suggest type="input" description="Enter custom model">Other</suggest>
</question>
```

ACP Schema:
```json
{
  "q0": {
    "type": "string",
    "title": "Model",
    "description": "Select equipment model:",
    "oneOf": [
      {"const": "SY215C", "title": "SY215C"},
      {"const": "SY365H", "title": "SY365H"}
    ]
  }
}
```

OpenCode Schema:
```json
{
  "questions": [{
    "header": "Model",
    "question": "Select equipment model:",
    "options": [
      {"label": "SY215C", "description": "21.5 ton excavator, popular model"},
      {"label": "SY365H", "description": "36.5 ton heavy-duty excavator"},
      {"label": "Other", "description": "Enter custom model"}
    ]
  }]
}
```

---

**2. Multi Select (`multi`)**

Tool XML:
```xml
<question header="Symptoms" type="multi">
  <text>Select all symptoms:</text>
  <suggest description="Engine exhaust is black, possible fuel issue">Black smoke</suggest>
  <suggest description="Reduced engine power output">Power loss</suggest>
  <suggest description="Unusual sounds from engine or hydraulics">Abnormal noise</suggest>
</question>
```

ACP Schema:
```json
{
  "q0": {
    "type": "array",
    "title": "Symptoms",
    "description": "Select all symptoms:",
    "items": {
      "type": "string",
      "enum": ["Black smoke", "Power loss"]
    },
    "uniqueItems": true
  }
}
```

OpenCode Schema:
```json
{
  "questions": [{
    "header": "Symptoms",
    "question": "Select all symptoms:",
    "multiple": true,
    "options": [
      {"label": "Black smoke", "description": "Engine exhaust is black, possible fuel issue"},
      {"label": "Power loss", "description": "Reduced engine power output"},
      {"label": "Abnormal noise", "description": "Unusual sounds from engine or hydraulics"}
    ]
  }]
}
```

---

**3. Text Input (`input`)**

Tool XML:
```xml
<question header="Notes" type="input">
  <text>Enter additional details:</text>
</question>
```

ACP Schema:
```json
{
  "q0": {
    "type": "string",
    "title": "Notes",
    "description": "Enter additional details:",
    "minLength": 1
  }
}
```

OpenCode Schema:
```json
{
  "questions": [{
    "header": "Notes",
    "question": "Enter additional details:",
    "options": [],
    "custom": true
  }]
}
```

#### ACP Schema Mapping

The tool converts XML questionnaire to MCP/ACP-compatible `ElicitRequestFormParams`:

```python
# Input: XML questionnaire
# Output: ACP ElicitRequestFormParams
{
  "mode": "form",
  "message": "Display message (constructed from questions)",
  "requestedSchema": {
    "type": "object",
    "properties": {
      "q0": { /* question 0 schema */ },
      "q1": { /* question 1 schema */ },
      ...
    },
    "required": ["q0", "q1", ...]
  }
}
```

#### Response Mapping

ACP responses use the three-action model (`accept` / `decline` / `cancel`).

The tool maps these to OpenCode-style responses:

| ACP Response | Tool Result | Content Example |
|--------------|-------------|-----------------|
| `action: "accept"` | Success | `"User has answered: ..."` |
| `action: "decline"` | Declined | `"User declined to answer"` |
| `action: "cancel"` | Cancelled | `"User cancelled the request"` |

### OpenCode Compatibility

The tool is designed to provide **OpenCode-compatible semantics** through the ACP transport layer.

| OpenCode Feature | Mapping to This Tool |
|------------------|---------------------|
| `questions[]` array | Multiple `<question>` tags |
| `question.header` | `header` attribute |
| `question.question` | `<text>` element |
| `question.options[]` | `<suggest>` elements |
| `question.multiple` | `type="multi"` |
| `custom: true` | `<suggest type="input">` |
| `answers[i]` array | `answers[i]` in metadata |

#### Key Differences from Native OpenCode

| Aspect | Native OpenCode | This Tool (ACP-based) |
|--------|-----------------|----------------------|
| Transport | Native TUI | MCP Elicit over ACP |
| Rendering | Client-side | Server-provided schema |
| Custom input | Auto-added | Explicit `<suggest type="input">` |
| Answer format | Native | ACP ElicitResult |

---

## Technical Design

### Architecture Overview

```
┌─────────────────┐
│  question_for_user Tool  │
│  - Parse XML            │
│  - Build Elicit Schema  │
└────────┬────────┘
         │
         ▼ ElicitRequest
┌─────────────────┐
│  ACP Server     │
│  - Render UI    │
│  - Collect answers    │
└────────┬────────┘
         │
         ▼ ElicitResult
┌─────────────────┐
│  Format Response       │
│  - Index answers       │
│  - Return metadata     │
└─────────────────┘
```

### XML Schema Specification

#### Field: `questionnaire`

Type: `string` (XML fragment, no XML declaration)

Structure:
```xml
<question header="string" type="enum|multi|input" required="true|false">
  <text>string</text>
  <suggest description="string">string</suggest>
  <suggest type="input" description="string">string</suggest>
</question>
<question ...>...</question>
```

**Note**: No XML declaration (`<?xml version="1.0"?>`) needed. Multiple `<question>` tags can appear sequentially without a wrapper element.

#### Element: `<suggest>`

Individual option within a question.

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `type` | `choice` \| `input` | `choice` | Option behavior type |
| `description` | string | - | Detailed explanation shown to user (optional) |
| `next_action` | string | - | Optional action trigger |

**Content**: Option label text (displayed to user, 1-5 words recommended)

**Example**:
```xml
<suggest description="21.5 ton excavator, popular model">SY215C</suggest>
<suggest description="36.5 ton heavy-duty excavator">SY365H</suggest>
<suggest type="input" description="Enter your own model number">Other model</suggest>
```

#### Question Types

| Type | Description | UI Rendering | Value Format |
|------|-------------|--------------|--------------|
| `enum` | Single choice from options | Dropdown/Radio | `[["label"]]` |
| `multi` | Multiple choices allowed | Checkboxes | `[["label1", "label2"]]` |
| `input` | Free text input | Text field | `[["user text"]]` |

#### Example Questionnaire

```xml
<question header="Model" type="enum">
  <text>What is the equipment model?</text>
  <suggest description="21.5 ton excavator, popular model">SY215C</suggest>
  <suggest description="36.5 ton heavy-duty excavator">SY365H</suggest>
  <suggest type="input" description="Enter custom model number">Other</suggest>
</question>

<question header="Symptoms" type="multi">
  <text>Select all symptoms observed:</text>
  <suggest description="Engine exhaust is black, possible fuel issue">Black smoke</suggest>
  <suggest description="Reduced engine power output">Power loss</suggest>
  <suggest description="Unusual sounds from engine or hydraulics">Abnormal noise</suggest>
</question>

<question header="Notes" type="input">
  <text>Any additional details?</text>
</question>
```

### Implementation Options Analysis

| Aspect | Option A: xml.etree | Option B: pydantic-xml |
|--------|---------------------|------------------------|
| Type Safety | ⚠️ Runtime only | ✅ Parse-time validation |
| Code Clarity | ⚠️ Manual dict access | ✅ Model attributes |
| IDE Support | ❌ Limited | ✅ Full autocomplete |
| Validation | ⚠️ Manual | ✅ Automatic (Pydantic) |
| Dependencies | ✅ Standard library | ⚠️ Additional package |
| Performance | ✅ Fast | ⚠️ Slight overhead (negligible) |
| Extensibility | ⚠️ Refactoring needed | ✅ Easy schema evolution |
| Error Messages | ⚠️ Generic | ✅ Structured ValidationError |

**Recommendation**: Use **Option B (pydantic-xml)** for production code due to type safety and maintainability benefits. Use Option A only if minimizing dependencies is critical.

---

### Implementation Options

#### Option A: Standard Library (xml.etree.ElementTree)

Simple, no additional dependencies.

```python
import xml.etree.ElementTree as ET
from dataclasses import dataclass

@dataclass
class ParsedQuestion:
    header: str
    type: str
    text: str
    options: list[Option]

def parse_questionnaire(xml: str) -> list[ParsedQuestion]:
    """Parse questionnaire XML using standard library."""
    wrapped = f"<root>{xml}</root>"
    root = ET.fromstring(wrapped)
    
    questions = []
    for q_elem in root.findall("question"):
        q = ParsedQuestion(
            header=q_elem.get("header", "Question"),
            type=q_elem.get("type", "enum"),
            text=q_elem.findtext("text", ""),
            options=_parse_options(q_elem),
        )
        questions.append(q)
    
    return questions
```

**Pros**: No dependencies, standard library  
**Cons**: No type validation, manual validation needed

---

#### Option B: Pydantic-XML (Recommended)

Type-safe XML parsing with validation.

```python
from pydantic_xml import BaseXmlModel, attr, element
from typing import Literal, List, Optional

class Suggest(BaseXmlModel, tag="suggest"):
    """An answer option within a question."""
    type: Literal["choice", "input"] = attr(default="choice")
    description: Optional[str] = attr(default=None)
    next_action: Optional[str] = attr(default=None)
    label: str  # element text content

class Question(BaseXmlModel, tag="question"):
    """A single question in the questionnaire."""
    header: str = attr()
    type: Literal["enum", "multi", "input"] = attr(default="enum")
    required: bool = attr(default=True)
    text: str = element(tag="text")
    options: List[Suggest] = element(tag="suggest", default=[])

class Questionnaire(BaseXmlModel, tag="questions"):
    """Container for multiple questions."""
    questions: List[Question] = element(tag="question")


def parse_questionnaire(xml: str) -> list[Question]:
    """Parse questionnaire XML using pydantic-xml.
    
    Wraps input in <questions> tag for single-root requirement.
    """
    wrapped = f"<questions>{xml}</questions>"
    questionnaire = Questionnaire.from_xml(wrapped)
    return questionnaire.questions


# With pydantic-xml, validation is automatic:
# - Invalid 'type' values raise ValidationError
# - Missing required elements raise ValidationError
# - Type coercion where possible
```

**Pros**: 
- Full type validation at parse time
- Clear model definitions
- IDE support (autocomplete, type checking)
- Easy to extend (add new fields, validation rules)
- Supports complex nested structures

**Cons**: 
- Additional dependency (`pydantic-xml`)
- Slight performance overhead (negligible for this use case)

---

#### Dependency Note

If using Option B, add to `pyproject.toml`:

```toml
[project.optional-dependencies]
xml = ["pydantic-xml>=2.0.0"]
```

Or core dependency if always using pydantic-xml parsing.

---

### Response Formatting

```python
def _format_response(
    questions: list[Question],  # or ParsedQuestion for Option A
    elicit_result: ElicitResult,
) -> ToolResult:
    """Format elicitation result into OpenCode-style response."""
    match elicit_result.action:
        case "accept":
            answers = _extract_answers(elicit_result.content, len(questions))
            
            formatted_parts = [
                f'"{q.text}" = "{", ".join(ans) if ans else "Unanswered"}"'
                for q, ans in zip(questions, answers)
            ]
            
            return ToolResult(
                content=f"User has answered your questions: {', '.join(formatted_parts)}",
                metadata={"answers": answers},
            )
            
        case "decline":
            return ToolResult(content="User declined to answer", metadata={"answers": []})
            
        case "cancel":
            return ToolResult(content="User cancelled the request", metadata={"answers": []})

def _extract_answers(content: dict, question_count: int) -> list[list[str]]:
    """Extract answers from ACP response."""
    answers = []
    for i in range(question_count):
        key = f"q{i}"
        raw = content.get(key)
        
        if isinstance(raw, list):
            answers.append(raw)
        elif raw is not None:
            answers.append([str(raw)])
        else:
            answers.append([])
    
    return answers
```

### Answer Format (OpenCode-style)

Following OpenCode's Question Tool pattern, the response to the agent is formatted as human-readable content, not a raw JSON structure.

**Content Format**:
```
User has answered your questions: "What is the equipment model?" = "SY215C", "Select all symptoms observed:" = "Black smoke, Power loss", "Any additional details?" = "Occurs at startup"
```

**Metadata Structure**:
```json
{
  "answers": [
    ["SY215C"],
    ["Black smoke", "Power loss"],
    ["Occurs at startup"]
  ]
}
```

- `answers[i]` corresponds to the i-th question in the questionnaire
- Each answer is an array of selected option labels
- For single-select questions, the array contains one element
- For skipped/unanswered questions, the array is empty `[]`

---

## Tool Schema Definition

### YAML Configuration

```yaml
name: question_for_user
description: |-
  Ask the user one or more structured questions in a single interaction.

  This tool allows agents to gather structured information from users efficiently by presenting
  multiple questions at once, each with predefined options (single choice, multiple choice)
  or free text input. Each question can include descriptive details to help users understand
  their choices.

  ### When to Use

  **Use this tool when you need to collect multiple related pieces of information:**

  1. **Multi-factor Clarification**
     - When multiple independent details are needed
     - Example: Equipment protocol + priority level + assignment preference

  2. **Systematic Information Collection**
     - When gathering structured data in a single interaction
     - Example: Equipment model + symptom type + occurrence time + severity

  3. **Preference Confirmation**
     - When confirming multiple user preferences
     - Example: Output format + detail level + language preference

  4. **Sequential Decision Points**
     - When multiple sequential choices must be made together
     - Example: Strategy selection + implementation approach + timeline preference

  ### Advantages over Single-Question Tools

  - **Fewer round-trips**: Collect multiple answers in one interaction
  - **Context preservation**: All questions are presented together for user reference
  - **Atomic decisions**: User sees the complete information landscape before answering
  - **Efficiency**: Reduces latency and improves user experience

  ### When NOT to Use

  - Sequential dependent questions (where question N depends on answer N-1)
  - Simple yes/no confirmations (use other tools)
  - Single piece of information (use ask_followup_question for simplicity)

  ### Usage Guidelines

  1. **Logical Grouping**: Group related questions together
  2. **Clear Descriptions**: Use `description` attributes to explain options
  3. **Mutually Exclusive Options**: Ensure options don't overlap
  4. **Include "Other"**: Always provide an escape hatch option
  5. **Order Matters**: Present questions in logical sequence

  ### Examples

  **Equipment Diagnosis**:
  ```xml
  <question header="Model" type="enum">
    <text>What is the equipment model?</text>
    <suggest description="21.5 ton excavator">SY215C</suggest>
    <suggest description="36.5 ton excavator">SY365H</suggest>
    <suggest type="input" description="Enter custom model">Other</suggest>
  </question>
  <question header="Symptoms" type="multi">
    <text>Select all observed symptoms:</text>
    <suggest description="Black exhaust smoke">Engine smoke</suggest>
    <suggest description="Reduced power output">Power loss</suggest>
  </question>
  ```

parameters:
  type: object
  properties:
    questionnaire:
      type: string
      description: |-
        XML-formatted questionnaire containing one or more questions.

        **Format Overview:**
        - One or more `<question>` elements (no wrapper required)
        - Each question has a header attribute and contains options
        - Options use `<suggest>` elements with optional descriptions

        **Question Attributes:**
        - `header` (required): Short label shown in UI (max 30 chars)
        - `type` (optional): Question type - `"enum"` | `"multi"` | `"input"`
          - `enum`: Single choice (dropdown/radio)
          - `multi`: Multiple choice (checkboxes)
          - `input`: Free text input
        - `required` (optional): Whether user must answer (default: true)

        **Suggest Attributes:**
        - `description` (optional): Detailed explanation of the option
        - `type` (optional): `"choice"` (default) | `"input"` | `"fill"`
        - `next_action` (optional): Tool to trigger after selection

        **Design Principles:**
        1. **Clarity**: Each question asks for ONE piece of information
        2. **Comparability**: Use description to help users distinguish similar options
        3. **Completeness**: Options should cover main scenarios plus an "Other" escape
        4. **Brevity**: Keep option labels concise (1-5 words), use description for details

        **XML Examples:**

        Single choice question:
        ```xml
        <question header="Priority" type="enum">
          <text>Select issue priority level:</text>
          <suggest description="Production stopped, immediate response">Critical</suggest>
          <suggest description="Major impact, respond within 1 hour">High</suggest>
          <suggest description="Minor impact, standard response">Normal</suggest>
        </question>
        ```

        Multiple choice question:
        ```xml
        <question header="Services" type="multi">
          <text>Select required services:</text>
          <suggest description="User authentication and authorization">Auth</suggest>
          <suggest description="Data persistence layer">Database</suggest>
          <suggest description="Performance optimization">Cache</suggest>
        </question>
        ```

        Text input question:
        ```xml
        <question header="Notes" type="input">
          <text>Additional details or context:</text>
        </question>
        ```

        **Common Patterns:**

        Model selection with custom input:
        ```xml
        <question header="Model" type="enum">
          <text>Equipment model:</text>
          <suggest description="21.5 ton excavator">SY215C</suggest>
          <suggest type="input" description="Enter model code">Other</suggest>
        </question>
        ```

        Severity with auto-trigger:
        ```xml
        <question header="Action" type="enum">
          <text>How to proceed?</text>
          <suggest next_action="attempt_completion" description="Submit final result">Complete</suggest>
          <suggest next_action="new_task" description="Request additional analysis">Delegate</suggest>
        </question>
        ```

        **Best Practices:**
        - Always provide meaningful descriptions for options
        - Order options by relevance or frequency (most common first)
        - Use "Other" with type="input" for edge cases
        - Keep total questionnaire under 5 questions for usability
        - Ensure question text is clear and unambiguous
  required:
    - questionnaire
strict: false
```

---

### MCP Elicit Schema Mapping

The tool converts XML questionnaire to ACP `requestedSchema` compatible with MCP Elicit:

```python
def _build_acp_schema(questions: list[ParsedQuestion]) -> dict[str, Any]:
    """Build MCP Elicit-compatible JSON Schema for multiple questions.
    
    Aligns with ACP Elicitation specification at:
    /packages/agent-client-protocol/docs/rfds/elicitation.mdx
    """
    properties: dict[str, Any] = {}
    
    for i, q in enumerate(questions):
        key = f"q{i}"
        
        if q.type == "input":
            # Free text input (string schema)
            properties[key] = {
                "type": "string",
                "title": q.header,
                "description": q.text,
                "minLength": 1,
            }
        elif q.type == "multi":
            # Multi-select (array with enum items)
            properties[key] = {
                "type": "array",
                "title": q.header,
                "description": q.text,
                "items": {
                    "type": "string",
                    "enum": [o.label for o in q.options if o.type == "choice"]
                },
                "uniqueItems": True,
            }
        else:  # enum (single select with oneOf for titles)
            properties[key] = {
                "type": "string",
                "title": q.header,
                "description": q.text,
                "oneOf": [
                    {"const": o.label, "title": o.label}
                    for o in q.options if o.type == "choice"
                ]
            }
    
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties.keys()),
    }


def _build_elicit_request(
    questions: list[ParsedQuestion]
) -> ElicitRequestFormParams:
    """Build ACP ElicitRequestFormParams from parsed questions."""
    schema = _build_acp_schema(questions)
    
    # Build display message from questions
    message_parts = []
    for i, q in enumerate(questions, 1):
        message_parts.append(f"{i}. {q.text}")
    
    return ElicitRequestFormParams(
        mode="form",  # ACP form mode
        message="\n".join(message_parts),
        requestedSchema=schema,
    )
```

---

## Implementation Plan

### Phase 1: Core Implementation

**Scope**: Tool implementation and basic parsing

**Deliverables**:
- `question_for_user.py` tool implementation
- XML parsing utilities
- Schema generation for MCP Elicit
- Basic error handling

**Dependencies**: None

### Phase 2: Provider Integration

**Scope**: AgentPool provider registration

**Deliverables**:
- `QuestionForUserProvider` class
- Tool schema YAML (`question_for_user.yaml`)
- Configuration examples

**Dependencies**: Phase 1

### Phase 3: Testing & Documentation

**Scope**: Validation and documentation

**Deliverables**:
- Unit tests for XML parsing
- Integration tests with ACP Server
- Usage examples in Prompt

**Dependencies**: Phase 2

### Milestones

| Milestone | Description | Target | Status |
|-----------|-------------|--------|--------|
| Core Tool | question_for_user implemented | Week 1 | Not Started |
| Provider Ready | Provider registered and configured | Week 1 | Not Started |
| Testing Complete | Unit + integration tests pass | Week 2 | Not Started |
| Documentation | Prompt and examples published | Week 2 | Not Started |

### Rollback Strategy

If issues arise:
1. Remove tool from agent configurations
2. Agents fall back to `ask_followup_question`
3. No data migration needed (runtime tool only)

---

## Open Questions

1. **Custom Input Handling**
   - Context: How to distinguish "select this option" from "enter custom text" in UI
   - Owner: Frontend team
   - Status: **RESOLVED**: Use `type="input"` attribute on suggest tags
   - Rationale: Aligns with OpenCode's `custom: true` behavior

2. **Required vs Optional Questions**
   - Context: Should all questions be required, or allow optional
   - Owner: Product
   - Status: Open
   - Proposed: Add `required="true|false"` attribute (default: true)

3. **XML Parsing Implementation**
   - Context: Choose between standard library and pydantic-xml
   - Owner: RFC-0010 implementer
   - Status: **RESOLVED**: Use pydantic-xml for type safety
   - Decision: Add `pydantic-xml>=2.0.0` as dependency; use Option B implementation
   - Rationale: Pydantic validation, IDE support, and maintainability outweigh dependency cost

4. **Validation Rules**
   - Context: Need input validation (min length, format) beyond JSON Schema
   - Owner: RFC-0010 implementer
   - Status: Out of scope for v1
   - Note: JSON Schema validation handled by ACP client; custom validation deferred to future RFC

5. **Image/Media Support**
   - Context: Questions that include images/diagrams
   - Owner: Architecture team
   - Status: Out of scope for v1
   - Note: Would require new XML elements (e.g., `<image src="..."/>`)

6. **Default Values**
   - Context: Should questions support pre-populated default answers
   - Owner: RFC-0010 implementer
   - Status: Open
   - Consideration: ACP Elicitation supports `default` in schema; could add `default` attribute to `<question>`
   - Trade-off: Increases LLM complexity (must specify defaults)

---

## Decision Record

> To be completed after RFC review

### Decision

**Status**: PENDING REVIEW

**Date**: 

**Approvers**:

### Decision Summary

[TBD after review]

### Key Discussion Points

[TBD after review]

### Conditions of Approval

[TBD after review]

### Dissenting Opinions

[TBD after review]

---

## References

### Internal Documents

- [RFC-0008: Ask Followup Question Tool](RFC-0008-ask-followup-question-tool.md)
- [OpenCode Question Tool Survey](/packages/xeno-agent/docs/survey/opencode/question-tool-survey.md)
- [AgentPool Tool Base](/packages/agentpool/src/agentpool/tools/base.py)

### External Resources

- [MCP Elicit Protocol](https://modelcontextprotocol.io/specification/2024-11-05/server/utilities/elicitation)
- [JSON Schema](https://json-schema.org/)

---

## Appendix

### A. Complete Example

**Agent Invocation**:

```python
await question_for_user({
    "questionnaire": '''<question header="Model" type="enum">
  <text>What is the equipment model?</text>
  <suggest>SY215C</suggest>
  <suggest>SY365H</suggest>
</question>
<question header="Symptom" type="multi">
  <text>Select symptoms:</text>
  <suggest>Black smoke</suggest>
  <suggest>Power loss</suggest>
</question>'''
})
```

**ACP Elicit Request** (translated from XML):

```json
{
  "mode": "form",
  "message": "1. What is the equipment model?\n2. Select symptoms:",
  "requestedSchema": {
    "type": "object",
    "properties": {
      "q0": {
        "type": "string",
        "title": "Model",
        "description": "What is the equipment model?",
        "oneOf": [
          {"const": "SY215C", "title": "SY215C"},
          {"const": "SY365H", "title": "SY365H"}
        ]
      },
      "q1": {
        "type": "array",
        "title": "Symptom",
        "description": "Select symptoms:",
        "items": {
          "type": "string",
          "enum": ["Black smoke", "Power loss"]
        },
        "uniqueItems": true
      }
    },
    "required": ["q0", "q1"]
  }
}
```

**User Sees** (rendered by ACP client):

```
1. What is the equipment model?
  [Dropdown: SY215C | SY365H]

2. Select symptoms:
  [ ] Black smoke
  [ ] Power loss

[Submit] [Cancel]
```

**ACP Response** (user submits):

```json
{
  "action": "accept",
  "content": {
    "q0": "SY215C",
    "q1": ["Black smoke", "Power loss"]
  }
}
```

**Agent Tool Result** (OpenCode-style formatting):

```
User has answered your questions: "What is the equipment model?" = "SY215C", "Select symptoms:" = "Black smoke, Power loss"
```

```json
{
  "metadata": {
    "answers": [
      ["SY215C"],
      ["Black smoke", "Power loss"]
    ]
  }
}
```

### B. Type Reference

| XML Attribute | Values | Default | Description |
|---------------|--------|---------|-------------|
| `type` (question) | `enum`, `multi`, `input` | `enum` | Question input type |
| `type` (suggest) | `choice`, `input` | `choice` | Option behavior |
| `header` | string | "Question" | Short label for UI |
| `required` | `true`, `false` | `true` | Whether answer required |
| `next_action` | string | - | Optional action trigger |

### C. Protocol Compatibility Summary

| Protocol Feature | Implementation |
|-----------------|----------------|
| ACP Elicitation | Form mode via `ElicitRequestFormParams` |
| MCP Alignment | Restricted JSON Schema per MCP draft spec |
| OpenCode Semantics | Response formatting and question structure |
| Answer Format | OpenCode-style content + `answers` metadata array |
