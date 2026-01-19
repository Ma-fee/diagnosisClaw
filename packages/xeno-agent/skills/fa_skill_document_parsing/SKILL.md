---
name: fa_skill_document_parsing
description: Extract specific information from technical documents.
allowed-tools:
  - search_engine
  - query_knowledge_base
---

# Document Parsing and Information Extraction

## Core Principle
Efficiently locate and extract precise technical data from large documents, manuals, and databases.

## Extraction Targets

### 1. Specifications
- Torque values, pressure settings, dimensions, capacities.
- **Format**: Extract value + unit + condition (e.g., "50 Nm @ 20°C").

### 2. Part Numbers
- OEM part numbers, supercessions, alternatives.
- **Verification**: Check validity for the specific machine serial number.

### 3. Procedures
- Step-by-step instructions, prerequisites, warnings.
- **Structure**: Maintain logical order.

## Methodology

1. **Search**: Locate relevant document sections.
2. **Filter**: Narrow down by model/serial number.
3. **Extract**: Copy exact values/text.
4. **Cite**: Provide document name, page, and version.

## Usage
Used primarily by Material Assistant to answer queries from other agents or users.
