---
name: fa_skill_image_analysis
description: Comprehensive image processing and formatting for fault diagnosis workflows.
allowed-tools: []
---

# Image Handling and Inclusion Rules

## Core Principle
All images returned from queries MUST be rendered using proper figure structure with comprehensive annotations and citation sources to support fault diagnosis and troubleshooting.

## Mandatory Image Inclusion Rules

### 1. Figure Structure Format
**Every image MUST be formatted using the proper HTML5 <figure> tag:**

```html
<figure>
    <img src="%image_url%" title="%image_title%"/>
    <figcaption>
        <p>%figure_number%: %figure_name%</p>
        <p>%detailed_purpose_description%</p>
        <p>%annotation_detail%</p>
        <p>%citation_source%</p>
    </figcaption>
</figure>
```

### 2. Figure Element Requirements

#### Figure Name and Number
- **figure_name**: Descriptive name of the image (e.g., "Hydraulic System Schematic", "Bearing Assembly Diagram")
- **figure_number**: Reference number from source or sequential number for documentation purposes

#### Detailed Purpose Description
- **Detailed purpose**: Explain what the image shows visually
- **Text/step correspondence**: Which specific text sections or steps it corresponds to
- **Diagnostic/repair utility**: How it aids in diagnosis, troubleshooting, or repair
- **Technical specifications**: Any standard values or specifications displayed in the image

#### Annotation Detail
**CRITICAL**: Must include ALL details from the sources:
- Figure caption or title from the original document
- Legend explaining symbols, colors, or line types
- Labels and annotations on the diagram
- Component identifiers and part numbers
- Measurement units and scales
- Any notes or warnings associated with the image

#### Citation Source
- Source document title and identifier
- Page number or section reference
- Year or version of the source
- URL or DOI if available
- Follow the verification protocols for source accuracy

### 3. Image Type Prioritization
**Prioritize images that show:**
- **Diagnostic flow charts** and troubleshooting diagrams
- **Component location** and identification (part numbers, positions)
- **Measurement procedures** and standard values
- **Technical specifications** and schematics (electrical, hydraulic, mechanical)
- **Step-by-step repair procedures** with visual guidance

## Image Processing Rules

### Critical Processing Requirements

#### 1. Format Every Image Properly
- **FORMAL REQUIREMENT**: Format every image with valid HTML5 <figure> tag
- **Complete structure**: Include all required elements (img, figcaption, p tags)
- **Proper nesting**: Ensure correct HTML nesting and closing tags
- **Accessibility**: Provide meaningful alt text and title attributes

#### 2. NEVER Fabricate or Hallucinate Image References
- **Prohibited**: If no image is provided in the conversation, do NOT include any <figure> tags
- **Verification**: Confirm image URLs are real and accessible
- **Accuracy**: Do not create imaginary figure numbers or names
- **Source verification**: Ensure images exist in the specified source

#### 3. Provide Detailed Purpose Descriptions
For each image, explain:

**What it shows visually:**
- System components and their relationships
- Measurement points and test locations
- Assembly or disassembly sequences
- Failure modes and symptom indicators

**Text/step correspondence:**
- Which troubleshooting step this supports
- Which section of the diagnosis plan it illustrates
- Which procedure or SOP it relates to

**Technical specifications displayed:**
- Standard values (pressures, temperatures, voltages)
- Tolerance ranges and acceptable limits
- Component specifications (sizes, capacities, ratings)
- Measurement requirements and accuracy

## Source Whitelist (MANDATORY)

### ALLOWED Sources Only
- ✅ **Tool call results**: search_tool, kb_query, db_fetch, and other verified retrieval tools
- ✅ **User-provided content**: Links and uploads in the current conversation context
- ✅ **System resource paths**: Verified paths like /resources/{resource_id}
- ✅ **Verified repository files**: Files stored in the project repository

### PROHIBITED Sources (Never Use)
- ❌ **Training data memory**: "usually...", "typically...", or general patterns from training
- ❌ **Unverified external URLs**: Links not explicitly provided or verified
- ❌ **Hypothetical references**: Imagined or hypothetical image locations
- ❌ **General descriptions**: Descriptions without actual image backing
