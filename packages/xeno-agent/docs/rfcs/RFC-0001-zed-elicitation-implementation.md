# RFC-0001: Implement ACP Elicitation Support in Zed

---

## Header Metadata

| Field | Value |
|-------|-------|
| **rfc_id** | RFC-0001 |
| **title** | Implement ACP Elicitation Support in Zed |
| **status** | DRAFT |
| **author** | @explore-agent (Research & Analysis) |
| **reviewers** | TBD |
| **created** | 2026-03-06 |
| **last_updated** | 2026-03-06 |
| **decision_date** | TBD |
| **related_rfc** | N/A |

---

## Overview

This RFC proposes the implementation of the Agent Client Protocol (ACP) Elicitation capability in Zed. Elicitation enables AI agents to ask users clarifying questions with structured input forms or redirect to external authentication flows via URLs. Currently, Zed lacks support for this feature, which limits the interactivity of AI agents and prevents them from gathering necessary context during sessions.

The implementation will add support for both `form` and `url` elicitation modes, enabling agents to present structured forms or OAuth/authentication flows to users. This aligns Zed with the ACP specification version `2025-11-25` and enhances the agent-user interaction paradigm.

**Expected Outcome**: Zed will be able to handle `session/elicitation` requests, render dynamic forms based on restricted JSON Schema, manage URL-mode authentication flows securely, and respond with the three-action model (accept/decline/cancel).

---

## Background & Context

### Current State of ACP in Zed

Zed currently implements the Agent Client Protocol with the following coverage:

- **Supported**: Basic messaging, tool calls, tool authorization
- **Partially Supported**: MCP (Model Context Protocol) features with Discovery and Sampling
- **Not Supported**: Elicitation

The current ACP crate version is `0.9.4`, which predates the Elicitation specification.

### Existing Alternative: Tool Authorization

Zed implements a `ToolAuthorization` system that serves a similar but more limited purpose:

```rust
pub enum PermissionOptions {
    Flat(Vec<acp::PermissionOption>),      // Simple allow/reject options
    Dropdown(Vec<PermissionOptionChoice>), // Granular selector
}
```

This system handles binary yes/no decisions for tool usage but lacks:
- Structured data collection capabilities
- Multi-field form rendering
- External URL redirection
- The three-action response model

**Key Implementation Pattern from Tool Authorization**:

The existing `ToolCallStatus::WaitingForConfirmation` state machine provides a proven pattern for Elicitation:

```rust
pub enum ToolCallStatus {
    WaitingForConfirmation {
        options: PermissionOptions,
        respond_tx: oneshot::Sender<acp::PermissionOptionId>,  // Key pattern
    },
    // ...
}
```

The authorization flow uses:
1. `request_tool_call_authorization()` (L1759-1791) - Creates `WaitingForConfirmation` status with `oneshot::Sender`
2. `authorize_tool_call()` (L1793-1823) - Sends response through channel, status transitions to `InProgress`
3. Events: `ToolAuthorizationRequested` → UI render → User action → `ToolAuthorizationReceived`

This pause-and-resume pattern with oneshot channels will be directly adapted for Elicitation.

### External Specifications

| Specification | Version | Status |
|---------------|---------|--------|
| ACP Elicitation | 2025-11-25 | RFD (Merged with 33 comments) |
| MCP Elicitation | Draft | In Development (SEP-1036 Final) |

### Glossary

| Term | Definition |
|------|------------|
| **ACP** | Agent Client Protocol - Protocol for AI agent communication |
| **Elicitation** | The capability for agents to ask users clarifying questions |
| **Form Mode** | Structured data collection using JSON Schema within the protocol |
| **URL Mode** | External redirection for sensitive operations (OAuth, payments) |
| **MCP** | Model Context Protocol - Related specification |
| **SFSafariViewController** | iOS secure browser context for URL mode |
| **oneshot::channel** | Rust async pattern for single-response communication |

---

## Problem Statement

### The Problem

1. **Limited Agent Interactivity**: AI agents in Zed cannot ask users for structured input or clarification during sessions. This forces agents to either make assumptions or abort tasks lacking sufficient context.

2. **Incompatibility with ACP Standard**: Zed's lack of Elicitation support means it cannot fully participate in ACP-compliant agent ecosystems. Agents expecting elicitation capabilities will fail or timeout.

3. **Manual Workarounds**: Users must manually interrupt agent flows or use external tools to provide context that could be collected through structured elicitation.

### Evidence

- **GitHub Issue #37307**: Reported that "MCP requests no longer visible... breaks elicitation flows (tools appear to stall or timeout)"
- **Official Documentation**: States "We welcome contributions that help advance Zed's MCP feature coverage (Discovery, Sampling, Elicitation, etc)"
- **No Existing Implementation**: Zero pull requests found specifically addressing Elicitation implementation

### Impact of Not Solving

| Aspect | Impact |
|--------|--------|
| **User Experience** | Agents cannot gather context, leading to incomplete or incorrect outputs |
| **Ecosystem Compatibility** | Zed cannot interoperate with ACP-compliant agents requiring elicitation |
| **Feature Gap** | Competitors supporting Elicitation provide superior agent experiences |

---

## Goals & Non-Goals

### Goals

1. **Full ACP Compliance**: Implement complete support for ACP Elicitation specification version `2025-11-25`
2. **Form Mode Support**: Enable structured data collection using restricted JSON Schema (string, number, integer, boolean, enum types)
3. **URL Mode Support**: Enable secure external authentication with SFSafariViewController (iOS) or system browser
4. **Three-Action Response Model**: Support `accept`, `decline`, and `cancel` responses
5. **Backward Compatibility**: Ensure existing Tool Authorization continues functioning unchanged

### Non-Goals

1. **Custom Schema Extensions**: Do not implement custom schema types beyond the restricted JSON Schema subset
2. **Nested Object Support**: Do not support nested objects or object arrays in Form mode (per spec restriction)
3. **Session Config Integration**: Do not merge Elicitation with existing Session Config Options (keep separate systems)
4. **Non-ACP Context**: Do not implement Elicitation outside of ACP sessions
5. **Auto-Progression**: Do not add automatic timeout or progression for pending elicitations
6. **MCP Alignment**: Do not change ACP method names to match MCP (`elicitation/create`) - keep ACP-native naming

### Success Criteria

| Criterion | Measure |
|-----------|---------|
| ACP Compliance | Passes all Elicitation test cases in ACP test suite |
| Form Rendering | Supports all restricted JSON Schema types |
| URL Security | Passes security review (no pre-fetch, explicit consent, HTTPS only) |
| User Experience | < 200ms latency from request to UI display |

---

## Evaluation Criteria

The following criteria will be used to evaluate implementation options:

| Criterion | Weight | Description | Minimum Threshold |
|-----------|--------|-------------|-------------------|
| **ACP Compliance** | High (30%) | Full adherence to ACP Elicitation spec (method names, schemas, responses) | 100% of required features |
| **Implementation Complexity** | High (25%) | Effort required for development and testing | Medium complexity |
| **User Experience** | High (25%) | Clarity and responsiveness of the interface | < 200ms latency |
| **Security** | Medium (10%) | Protection against SSRF, phishing, malicious URLs | Pass security review |
| **Maintainability** | Medium (10%) | Code clarity and future extension ease | Well-documented, tested |

---

## Options Analysis

### Option 1: Extend Existing Tool Authorization System

**Description**: Modify the existing `ToolAuthorization` system to support elicitation by adding new `PermissionOptions` variants and expanding the response model.

**Advantages**:
- Leverages existing UI components (`render_permission_buttons`, L5705-5781)
- Lower initial development effort (reuse `ThreadView::render_tool_call` pattern)
- Familiar patterns for existing developers (`allow_tool_use` callbacks)
- Minimal changes to architecture

**Disadvantages**:
- Tool Authorization is tool-call scoped, while Elicitation is session-scoped
- `PermissionOptions` enum doesn't support JSON Schema-based forms
- Difficult to cleanly support three-action model vs binary Allow/Reject
- Violates separation of concerns - different semantics forced into same structure
- Cannot cleanly handle URL mode with security requirements

**Evaluation Against Criteria**:

| Criterion | Score | Notes |
|-----------|-------|-------|
| ACP Compliance | 4/10 | Method names wrong, session vs tool scope mismatch |
| Implementation Complexity | 7/10 | Lower initial but high maintenance |
| User Experience | 6/10 | Reuses familiar UI but limits flexibility |
| Security | 5/10 | URL mode security hard to retrofit |
| Maintainability | 4/10 | Creates coupled, divergent dependencies |
| **Weighted Total** | **5.2/10** | |

**Effort Estimate**: 2-3 weeks initial, ongoing maintenance burden

**Risk Assessment**: High - Accumulates technical debt, architectural debt from scope mismatch

---

### Option 2: Parallel Implementation Alongside Tool Authorization (RECOMMENDED)

**Description**: Implement Elicitation as a completely separate system with its own state machine, events, and UI components, running in parallel to Tool Authorization.

**Advantages**:
- Clean separation of concerns
- Full ACP spec compliance without compromises (`session/elicitation` method)
- Directly adapts proven oneshot channel pattern from Tool Authorization
- Independent evolution of both systems
- Easier testing and debugging (separate `ElicitationStatus` from `ToolCallStatus`)
- Better long-term maintainability

**Disadvantages**:
- Higher initial implementation effort
- Some code duplication (event handling patterns, UI layout)
- Requires larger architectural changes (new files: `elicitation.rs`, `elicitation_form.rs`)
- More modules to maintain

**Evaluation Against Criteria**:

| Criterion | Score | Notes |
|-----------|-------|-------|
| ACP Compliance | 10/10 | Full spec compliance, correct method names and schemas |
| Implementation Complexity | 5/10 | More components but guided by existing patterns |
| User Experience | 9/10 | Clean, dedicated UI for each use case |
| Security | 9/10 | Purpose-built security controls for URL mode |
| Maintainability | 9/10 | Clear boundaries, follows existing ACP patterns |
| **Weighted Total** | **8.5/10** | |

**Effort Estimate**: 4-6 weeks

**Risk Assessment**: Low - Clean architecture, follows proven patterns from Tool Authorization

---

### Option 3: Unified Input System with Mode Switching

**Description**: Create a generic "User Input" system that can switch between Tool Authorization, Form Elicitation, URL Elicitation, and potentially Session Config modes.

**Advantages**:
- Maximizes code reuse
- Consistent user experience across all input types
- Single point for UI styling and theming
- Easier to add future input modes

**Disadvantages**:
- Additional abstraction complexity
- May obscure distinct purposes (authorization vs clarification vs OAuth)
- Risk of over-generalization
- More complex testing matrix
- Refactoring existing Tool Authorization adds risk

**Evaluation Against Criteria**:

| Criterion | Score | Notes |
|-----------|-------|-------|
| ACP Compliance | 7/10 | Requires abstraction to not lose spec details |
| Implementation Complexity | 3/10 | Highest abstraction complexity, refactoring risk |
| User Experience | 7/10 | Consistent but may lose mode-specific optimizations |
| Security | 6/10 | Generic system may miss mode-specific requirements |
| Maintainability | 6/10 | Complex abstractions harder to reason about |
| **Weighted Total** | **5.8/10** | |

**Effort Estimate**: 6-8 weeks (including refactoring existing systems)

**Risk Assessment**: High - Over-engineering, refactoring existing working code

---

## Recommendation

**Recommended Option**: **Option 2 - Parallel Implementation**

### Justification

Based on the evaluation criteria, Option 2 scores highest (8.5/10) due to:

1. **Full ACP Compliance**: Achieves 100% specification compliance with correct `session/elicitation` method, JSON Schema support, and three-action response model
2. **Proven Pattern Adaptation**: Successfully adapts the oneshot channel pattern from `ToolAuthorization` (`respond_tx: oneshot::Sender`)
3. **Clean Semantics**: Users and developers can distinguish between tool authorization (binary, tool-scoped) and elicitation (structured, session-scoped)
4. **Security**: Dedicated implementation allows proper URL validation (HTTPS only, SSRF protection) and secure browser context (SFSafariViewController)
5. **Maintainability**: Clear boundaries match the separation between `AcpThreadEvent::ToolAuthorizationRequested` and new `ElicitationRequested` events

### Trade-offs Being Accepted

- **Higher Initial Effort**: 4-6 weeks vs 2-3 weeks for Option 1
- **Some Code Duplication**: Event handling and UI layout patterns similar to Tool Authorization
- **Larger Codebase**: New files: `elicitation.rs`, `elicitation_form.rs`, `elicitation_url.rs`

These trade-offs are acceptable given the architectural clarity and long-term maintainability benefits.

### Alternative Consideration

Option 1 (Extend Tool Authorization) could be considered only if:
- Time-to-market is critical (< 2 weeks hard deadline)
- Implementation limited to minimal Form mode only
- A clear migration path to Option 2 in follow-up PR is acceptable

However, given the session-scoped vs tool-scoped fundamental difference, this introduces significant architectural debt that will require refactoring later.

---

## Technical Design

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Zed Editor                                      │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                      Frontend (GPUI)                                   │  │
│  │  ┌────────────────┐  ┌──────────────┐  ┌──────────────────────────┐   │  │
│  │  │   ToolAuth     │  │  Elicitation │  │     Connection UI        │   │  │
│  │  │     UI         │  │     UI       │  │                          │   │  │
│  │  │ (existing)     │  │  (new)       │  │ (thread_view.rs)         │   │  │
│  │  └────────────────┘  └──────────────┘  └──────────────────────────┘   │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                      │                                       │
│  ┌───────────────────────────────────┼───────────────────────────────────┐  │
│  │                      Event Layer   │                                   │  │
│  │  AcpThreadEvent::ToolAuthorizationRequested    (existing)            │  │
│  │  AcpThreadEvent::ToolAuthorizationReceived       (existing)          │  │
│  │  AcpThreadEvent::ElicitationRequested    ←── NEW                     │  │
│  │  AcpThreadEvent::ElicitationResponded    ←── NEW                     │  │
│  └───────────────────────────────────┼───────────────────────────────────┘  │
│                                      │                                       │
│  ┌───────────────────────────────────┼───────────────────────────────────┐  │
│  │                      Backend (ACP) │                                   │  │
│  │  ┌────────────────┐               │    ┌──────────────────────────┐   │  │
│  │  │    acp_        │◄──────────────┴────┤   AcpThread              │   │  │
│  │  │   thread       │                    │                          │   │  │
│  │  │   .rs          │                    │ • request_elicitation()  │   │  │
│  │  │                │                    │ • submit_elicitation()   │   │  │
│  │  │ ToolCallStatus │                    │ • ElicitationStatus      │   │  │
│  │  │   ::Waiting... │                    │   ::WaitingForUser       │   │  │
│  │  └────────────────┘                    │   + oneshot::Sender      │   │  │
│  │                                        └──────────────────────────┘   │  │
│  │  ┌────────────────┐  ┌──────────────────────────────────────────┐     │  │
│  │  │   agent_       │  │  elicitation.rs ←── NEW                  │     │  │
│  │  │  connection    │  │  • ElicitationRequest                    │     │  │
│  │  │   .rs          │  │  • ElicitationResponse                   │     │  │
│  │  │                │  │  • ElicitationStatus                     │     │  │
│  │  │ • AgentConn.   │  │  • RestrictedJsonSchema                  │     │  │
│  │  │   trait        │  └──────────────────────────────────────────┘     │  │
│  │  └────────────────┘                                                   │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                               │
                    ACP Server (session/elicitation)
```

### Core Data Structures

#### ElicitationRequest

```rust
/// Unique identifier for elicitation requests
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct ElicitationId(pub(crate) usize);

/// Represents an elicitation request from the agent
#[derive(Clone, Debug)]
pub struct ElicitationRequest {
    /// Unique identifier for this elicitation
    pub id: ElicitationId,
    
    /// The session this elicitation belongs to
    pub session_id: SessionId,
    
    /// Elicitation mode: form or url
    pub mode: ElicitationMode,
    
    /// Human-readable message/prompt
    pub message: SharedString,
    
    /// Server-provided identifier for tracking (URL mode)
    pub elicitation_id: Option<String>,
}

#[derive(Clone, Debug)]
pub enum ElicitationMode {
    Form {
        /// Restricted JSON Schema defining the requested data
        requested_schema: RestrictedJsonSchema,
    },
    Url {
        /// URL to open in secure browser context
        url: String,
    },
}
```

#### ElicitationResponse

```rust
/// User response to an elicitation request
#[derive(Clone, Debug)]
pub struct ElicitationResponse {
    /// Reference to the original request
    pub request_id: ElicitationId,
    
    /// The user's chosen action (three-action model)
    pub action: ElicitationAction,
}

#[derive(Clone, Debug)]
pub enum ElicitationAction {
    Accept {
        /// Form data (for Form mode) or empty (for URL mode)
        content: serde_json::Value,
    },
    Decline,
    Cancel,
}
```

#### State Machine (Adapted from ToolAuthorization Pattern)

```rust
/// Elicitation status state machine - mirrors ToolCallStatus pattern
pub enum ElicitationStatus {
    /// No active elicitation
    Idle,
    
    /// Elicitation requested, waiting for user response
    /// Adapted from ToolCallStatus::WaitingForConfirmation
    WaitingForUser {
        request: ElicitationRequest,
        /// One-shot channel for async response - KEY PATTERN from ToolAuthorization
        respond_tx: oneshot::Sender<ElicitationResponse>,
        timestamp: Instant,
    },
    
    /// User has responded, processing
    Responding,
    
    /// Elicitation completed
    Completed,
}
```

### Backend Implementation

#### ACP Thread Integration

In `crates/acp_thread/src/acp_thread.rs`:

```rust
impl AcpThread {
    /// Handle incoming elicitation request from ACP server
    /// Mirrors request_tool_call_authorization() pattern (L1759-1791)
    fn handle_elicitation_request(
        &mut self,
        request: ElicitationRequest,
    ) -> Task<Result<()>> {
        // Validate session exists
        let session = self.sessions.get(&request.session_id)
            .ok_or(ElicitationError::InvalidSession)?;
        
        // Create one-shot channel for async response (KEY PATTERN)
        let (respond_tx, respond_rx) = oneshot::channel();
        
        // Update state to WaitingForUser with channel
        session.elicitation_status = ElicitationStatus::WaitingForUser {
            request: request.clone(),
            respond_tx,
            timestamp: Instant::now(),
        };
        
        // Emit event to frontend - mirrors ToolAuthorizationRequested
        self.emit(AcpThreadEvent::ElicitationRequested(request));
        
        // Return task that waits for response
        cx.spawn(async move {
            match respond_rx.await {
                Ok(response) => Ok(response),
                Err(_) => Err(ElicitationError::ChannelClosed),
            }
        })
    }
    
    /// Handle user response to elicitation
    /// Mirrors authorize_tool_call() pattern (L1793-1823)
    fn submit_elicitation_response(
        &mut self,
        response: ElicitationResponse,
    ) -> Result<()> {
        // Get session and current status
        let session = self.current_session()?;
        
        // Extract the respond_tx channel
        let respond_tx = match std::mem::replace(
            &mut session.elicitation_status,
            ElicitationStatus::Responding,
        ) {
            ElicitationStatus::WaitingForUser { respond_tx, .. } => respond_tx,
            _ => return Err(ElicitationError::NotWaitingForResponse),
        };
        
        // Send response through channel (KEY PATTERN)
        let _ = respond_tx.send(response.clone());
        
        // Update final state
        session.elicitation_status = ElicitationStatus::Completed;
        
        // Emit completion event
        self.emit(AcpThreadEvent::ElicitationResponded(response));
        
        Ok(())
    }
}
```

#### Connection Trait Extension

In `crates/acp_thread/src/connection.rs`:

```rust
pub trait AgentConnection: Send + Sync {
    // Existing methods...
    fn prompt(&self, user_message_id: Option<UserMessageId>, params: acp::PromptRequest, cx: &mut App) 
        -> Task<Result<acp::PromptResponse>>;
    fn cancel(&self, session_id: &acp::SessionId, cx: &mut App);
    fn auth_methods(&self) -> &[acp::AuthMethod];
    
    // NEW: Elicitation methods
    fn request_elicitation(
        &self, 
        request: ElicitationRequest
    ) -> Task<Result<ElicitationResponse>>;
    
    fn cancel_elicitation(
        &self, 
        request_id: ElicitationId
    ) -> Task<Result<()>>;
}
```

#### Event Types Extension

```rust
pub enum AcpThreadEvent {
    // Existing events...
    ToolAuthorizationRequested(acp::ToolCallId),
    ToolAuthorizationReceived(acp::ToolCallId),
    
    // NEW: Elicitation events
    /// An elicitation has been requested - mirrors ToolAuthorizationRequested
    ElicitationRequested(ElicitationRequest),
    
    /// User has responded to an elicitation - mirrors ToolAuthorizationReceived
    ElicitationResponded(ElicitationResponse),
    
    /// Elicitation was cancelled (timeout, user action, or error)
    ElicitationCancelled(ElicitationId),
}
```

### Frontend Implementation

#### Form Mode UI Component

In `crates/agent_ui/src/connection_view/elicitation_form.rs`:

```rust
/// Renders a form based on restricted JSON Schema
pub struct ElicitationForm {
    request: ElicitationRequest,
    form_data: HashMap<String, serde_json::Value>,
    validation_errors: Vec<String>,
}

impl ElicitationForm {
    fn new(request: ElicitationRequest) -> Self {
        // Pre-populate with defaults from schema
        let form_data = match &request.mode {
            ElicitationMode::Form { requested_schema } => {
                requested_schema.extract_defaults()
            }
            _ => HashMap::new(),
        };
        
        Self {
            request,
            form_data,
            validation_errors: Vec::new(),
        }
    }
}

impl Render for ElicitationForm {
    fn render(&mut self, window: &mut Window, cx: &mut Context<Self>) -> impl IntoElement {
        div()
            .flex()
            .flex_col()
            .gap_2()
            .child(self.render_header())
            .child(self.render_message())
            .child(self.render_form_fields())
            .child(self.render_actions())
    }
    
    fn render_form_fields(&self) -> impl IntoElement {
        match &self.request.mode {
            ElicitationMode::Form { requested_schema } => {
                div()
                    .flex()
                    .flex_col()
                    .gap_3()
                    .children(
                        requested_schema.properties.iter().map(|(name, schema)| {
                            self.render_field(name, schema)
                        })
                    )
            }
            _ => div(),
        }
    }
    
    fn render_field(&self, name: &str, schema: &SchemaProperty) -> impl IntoElement {
        match schema.property_type {
            SchemaType::String => self.render_string_field(name, schema),
            SchemaType::Number => self.render_number_field(name, schema),
            SchemaType::Integer => self.render_integer_field(name, schema),
            SchemaType::Boolean => self.render_boolean_field(name, schema),
            SchemaType::Enum { options } => self.render_enum_field(name, options, schema),
        }
    }
    
    fn render_string_field(&self, name: &str, schema: &SchemaProperty) -> impl IntoElement {
        let value = self.form_data.get(name)
            .and_then(|v| v.as_str())
            .unwrap_or_default();
        
        div()
            .flex()
            .flex_col()
            .gap_1()
            .child(Label::new(schema.title.as_deref().unwrap_or(name)))
            .child(
                TextInput::new(name)
                    .value(value)
                    .placeholder(schema.description.as_deref().unwrap_or_default())
                    .on_change(cx.listener(move |this, new_value, _window, _cx| {
                        this.form_data.insert(
                            name.to_string(),
                            serde_json::Value::String(new_value.to_string()),
                        );
                    }))
            )
    }
    
    fn render_actions(&self) -> impl IntoElement {
        div()
            .flex()
            .gap_2()
            .child(
                Button::new("submit", "Submit")
                    .on_click(cx.listener(|this, _, window, cx| {
                        if this.validate() {
                            this.submit(ElicitationAction::Accept {
                                content: serde_json::to_value(&this.form_data).unwrap(),
                            }, cx);
                        }
                    }))
            )
            .child(
                Button::new("decline", "Decline")
                    .style(ButtonStyle::Secondary)
                    .on_click(cx.listener(|this, _, window, cx| {
                        this.submit(ElicitationAction::Decline, cx);
                    }))
            )
            .child(
                Button::new("cancel", "Cancel")
                    .style(ButtonStyle::Ghost)
                    .on_click(cx.listener(|this, _, window, cx| {
                        this.submit(ElicitationAction::Cancel, cx);
                    }))
            )
    }
}
```

#### URL Mode UI Component

In `crates/agent_ui/src/connection_view/elicitation_url.rs`:

```rust
/// Renders URL elicitation with security confirmations
pub struct ElicitationUrl {
    request: ElicitationRequest,
}

impl ElicitationUrl {
    fn render_security_warning(&self) -> impl IntoElement {
        div()
            .flex()
            .gap_2()
            .child(Icon::new(IconName::Lock))
            .child(Label::new("External authentication required"))
    }
    
    fn render_url_display(&self, url: &str) -> impl IntoElement {
        // Display full URL, NOT as clickable link
        div()
            .font_mono()
            .bg(rgb(0xf5f5f5))
            .p_2()
            .rounded_md()
            .child(url)
            .tooltip(move |cx| Tooltip::text("Verify this URL before proceeding", cx))
    }
    
    fn render_domain_highlight(&self, url: &str) -> Option<impl IntoElement> {
        let parsed = Url::parse(url).ok()?;
        let domain = parsed.host_str()?;
        
        div()
            .flex()
            .gap_2()
            .child(Label::new("Domain:"))
            .child(
                Label::new(domain)
                    .font_weight(FontWeight::SEMIBOLD)
                    .color(cx.theme().colors().text_accent)
            )
    }
}

impl Render for ElicitationUrl {
    fn render(&mut self, window: &mut Window, cx: &mut Context<Self>) -> impl IntoElement {
        let url = match &self.request.mode {
            ElicitationMode::Url { url } => url,
            _ => return div(),
        };
        
        div()
            .flex()
            .flex_col()
            .gap_4()
            .child(self.render_security_warning())
            .child(self.render_message())
            .child(self.render_url_display(url))
            .child(self.render_domain_highlight(url))
            .child(
                Label::new("⚠️ This will open in your default browser")
                    .color(cx.theme().colors().text_warning)
            )
            .child(self.render_actions())
    }
    
    fn render_actions(&self) -> impl IntoElement {
        let url = match &self.request.mode {
            ElicitationMode::Url { url } => url.clone(),
            _ => return div(),
        };
        
        div()
            .flex()
            .gap_2()
            .child(
                Button::new("open-externally", "Open in Browser")
                    .on_click(cx.listener(move |this, _, window, cx| {
                        // Open in secure browser context
                        cx.open_url(&url);
                        
                        // Return accept immediately per spec
                        this.submit(ElicitationAction::Accept {
                            content: serde_json::Value::Null,
                        }, cx);
                    }))
            )
            .child(
                Button::new("cancel", "Cancel")
                    .style(ButtonStyle::Ghost)
                    .on_click(cx.listener(|this, _, window, cx| {
                        this.submit(ElicitationAction::Cancel, cx);
                    }))
            )
    }
}
```

#### Thread View Integration

In `crates/agent_ui/src/connection_view/thread_view.rs`, integrated with existing `render_tool_call`:

```rust
impl ThreadView {
    /// Main render method - check for elicitation alongside tool calls
    fn render_conversation(&self, window: &mut Window, cx: &mut Context<Self>) -> impl IntoElement {
        div()
            .children(
                self.model.read(cx).entries.iter().enumerate().map(|(ix, entry)| {
                    self.render_entry(ix, entry, window, cx)
                })
            )
            .child(self.render_elicitation_if_needed(window, cx))  // NEW
    }
    
    /// Render pending elicitation if present
    fn render_elicitation_if_needed(
        &self,
        window: &mut Window,
        cx: &mut Context<Self>,
    ) -> impl IntoElement {
        match self.model.read(cx).elicitation_status {
            ElicitationStatus::WaitingForUser { ref request, .. } => {
                match &request.mode {
                    ElicitationMode::Form { .. } => {
                        div()
                            .child(ElicitationForm::new(request.clone()))
                    }
                    ElicitationMode::Url { .. } => {
                        div()
                            .child(ElicitationUrl::new(request.clone()))
                    }
                }
            }
            _ => div().hidden(),
        }
    }
}
```

### JSON Schema Validation

```rust
/// Validates that a schema complies with restricted JSON Schema subset
pub struct SchemaValidator;

impl SchemaValidator {
    pub fn validate(schema: &serde_json::Value) -> Result<RestrictedJsonSchema> {
        // Validate root is object type
        let schema_type = schema.get("type")
            .and_then(|t| t.as_str())
            .ok_or(SchemaError::MissingType)?;
        
        if schema_type != "object" {
            return Err(SchemaError::InvalidRootType);
        }
        
        // Validate properties
        let properties = schema.get("properties")
            .and_then(|p| p.as_object())
            .ok_or(SchemaError::MissingProperties)?;
        
        for (name, prop_schema) in properties {
            Self::validate_property(name, prop_schema)?;
        }
        
        // Check no unsupported features
        Self::check_no_unsupported_features(schema)?;
        
        Ok(RestrictedJsonSchema {
            properties: /* ... */,
        })
    }
    
    fn validate_property(name: &str, schema: &serde_json::Value) -> Result<()> {
        let prop_type = schema.get("type")
            .and_then(|t| t.as_str())
            .ok_or(SchemaError::MissingPropertyType)?;
        
        match prop_type {
            "string" => Self::validate_string_schema(schema)?,
            "number" => Self::validate_number_schema(schema)?,
            "integer" => Self::validate_integer_schema(schema)?,
            "boolean" => Self::validate_boolean_schema(schema)?,
            "array" => Self::validate_array_schema(schema)?,  // For multi-select enums
            _ => return Err(SchemaError::UnsupportedType(prop_type.to_string())),
        }
        
        Ok(())
    }
    
    fn validate_string_schema(schema: &serde_json::Value) -> Result<()> {
        // Allow: type, title, description, minLength, maxLength, pattern, format, default
        // Deny: anything else
        let allowed = [
            "type", "title", "description", "minLength", "maxLength", 
            "pattern", "format", "default"
        ];
        
        Self::check_only_allowed_keys(schema, &allowed)?;
        
        // Validate format if present
        if let Some(format) = schema.get("format").and_then(|f| f.as_str()) {
            match format {
                "email" | "uri" | "date" | "date-time" => Ok(()),
                _ => Err(SchemaError::UnsupportedFormat(format.to_string())),
            }?;
        }
        
        Ok(())
    }
    
    fn check_no_unsupported_features(schema: &serde_json::Value) -> Result<()> {
        let unsupported = ["additionalProperties", "$ref", "anyOf", "allOf", "not"];
        for key in &unsupported {
            if schema.get(key).is_some() {
                return Err(SchemaError::UnsupportedFeature(key.to_string()));
            }
        }
        Ok(())
    }
}
```

### URL Security Validation

```rust
/// Validates URLs for SSRF and security issues
pub fn validate_elicitation_url(url: &str) -> Result<()> {
    let parsed = Url::parse(url)
        .map_err(|_| ElicitationError::InvalidUrl)?;
    
    // 1. Only HTTPS allowed
    if parsed.scheme() != "https" {
        return Err(ElicitationError::InsecureProtocol);
    }
    
    // 2. Must have a host
    let host = parsed.host_str()
        .ok_or(ElicitationError::MissingHost)?;
    
    // 3. SSRF protection: block private/internal IPs
    if let Ok(addr) = host.parse::<IpAddr>() {
        if addr.is_private() || addr.is_loopback() || addr.is_unspecified() {
            return Err(ElicitationError::PrivateNetwork);
        }
    }
    
    // 4. Block localhost names
    if host == "localhost" || host.ends_with(".local") {
        return Err(ElicitationError::PrivateNetwork);
    }
    
    // 5. Block link-local addresses
    if host.starts_with("fe80:") || host.starts_with("169.254.") {
        return Err(ElicitationError::PrivateNetwork);
    }
    
    Ok(())
}
```

### Protocol Integration

#### Capability Declaration

```rust
fn initialize_capabilities() -> ClientCapabilities {
    ClientCapabilities {
        // Existing capabilities...
        elicitation: Some(ElicitationCapabilities {
            form: Some(ElicitationFormCapabilities {}),
            url: Some(ElicitationUrlCapabilities {}),
        }),
    }
}

/// Note: Empty object `{}` equals `{ form: {} }` for backwards compatibility
fn minimal_elicitation_capabilities() -> ClientCapabilities {
    ClientCapabilities {
        elicitation: Some(ElicitationCapabilities {
            form: Some(ElicitationFormCapabilities {}),
            url: None,  // Not supporting URL mode
        }),
    }
}
```

#### Request Handler

```rust
fn handle_session_elicitation(&self, params: ElicitationParams) -> Result<ElicitationResult> {
    // Validate mode is supported
    match params.mode {
        "form" => self.capabilities.elicitation.form.as_ref()
            .ok_or(ElicitationError::UnsupportedMode("form"))?,
        "url" => self.capabilities.elicitation.url.as_ref()
            .ok_or(ElicitationError::UnsupportedMode("url"))?,
        _ => return Err(ElicitationError::InvalidMode),
    };
    
    let request = ElicitationRequest {
        id: ElicitationId::new(),
        session_id: params.session_id,
        mode: match params.mode {
            "form" => ElicitationMode::Form {
                requested_schema: SchemaValidator::validate(&params.requested_schema)?,
            },
            "url" => {
                let url = params.url.ok_or(ElicitationError::MissingUrl)?;
                validate_elicitation_url(&url)?;
                ElicitationMode::Url { url }
            }
            _ => return Err(ElicitationError::InvalidMode),
        },
        message: params.message.into(),
        elicitation_id: params.elicitation_id,
    };
    
    // Dispatch to session and wait for response using oneshot pattern
    let response = self.request_elicitation(request)?;
    
    Ok(ElicitationResult {
        action: response.action,
        content: match response.action {
            ElicitationAction::Accept { content } => Some(content),
            _ => None,
        }
    })
}
```

---

## Implementation Plan

### Phase 1: Foundation & Backend (Week 1-2)

**Goals**: Establish core data structures and backend message handling

| Task | Owner | Duration | Dependencies | File(s) Affected |
|------|-------|----------|--------------|------------------|
| 1.1 Upgrade ACP crate to Elicitation-supporting version | Backend | 2 days | None | `Cargo.toml` |
| 1.2 Define `ElicitationRequest`, `ElicitationResponse`, `ElicitationId` types | Backend | 1 day | 1.1 | `crates/acp_thread/src/elicitation.rs` |
| 1.3 Define `ElicitationStatus` state machine with oneshot pattern | Backend | 1 day | 1.2 | `crates/acp_thread/src/elicitation.rs` |
| 1.4 Extend `AcpThread` with `handle_elicitation_request()` | Backend | 2 days | 1.3 | `crates/acp_thread/src/acp_thread.rs` |
| 1.5 Add `submit_elicitation_response()` method | Backend | 1 day | 1.4 | `crates/acp_thread/src/acp_thread.rs` |
| 1.6 Add `AcpThreadEvent::ElicitationRequested/Responded` variants | Backend | 1 day | 1.3 | `crates/acp_thread/src/acp_thread.rs` |
| 1.7 Extend `AgentConnection` trait with elicitation methods | Backend | 1 day | 1.2 | `crates/acp_thread/src/connection.rs` |
| 1.8 Implement `elicitation.rs` module | Backend | 2 days | 1.2-1.7 | `crates/acp_thread/src/elicitation.rs` |
| 1.9 Unit tests for backend handlers | Backend | 2 days | 1.4-1.8 | `crates/acp_thread/src/elicitation_tests.rs` |

**Deliverable**: Backend can receive and process elicitation requests, emit events, and send responses

### Phase 2: Form Mode UI (Week 3-4)

**Goals**: Implement Form mode rendering and interaction

| Task | Owner | Duration | Dependencies | File(s) Affected |
|------|-------|----------|--------------|------------------|
| 2.1 Implement `RestrictedJsonSchema` types | Frontend | 1 day | 1.2 | `crates/acp_thread/src/elicitation.rs` |
| 2.2 Implement `SchemaValidator` | Frontend | 2 days | 2.1 | `crates/acp_thread/src/schema_validator.rs` |
| 2.3 Create `ElicitationForm` component structure | Frontend | 1 day | 2.1 | `crates/agent_ui/src/connection_view/elicitation_form.rs` |
| 2.4 Implement `render_string_field()` | Frontend | 1 day | 2.3 | `crates/agent_ui/src/connection_view/elicitation_form.rs` |
| 2.5 Implement `render_number_field()` and `render_integer_field()` | Frontend | 1 day | 2.3 | `crates/agent_ui/src/connection_view/elicitation_form.rs` |
| 2.6 Implement `render_boolean_field()` | Frontend | 1 day | 2.3 | `crates/agent_ui/src/connection_view/elicitation_form.rs` |
| 2.7 Implement `render_enum_field()` (single & multi-select) | Frontend | 2 days | 2.3 | `crates/agent_ui/src/connection_view/elicitation_form.rs` |
| 2.8 Add form validation | Frontend | 2 days | 2.4-2.7 | `crates/agent_ui/src/connection_view/elicitation_form.rs` |
| 2.9 Implement three-action buttons (Submit/Decline/Cancel) | Frontend | 1 day | 2.3 | `crates/agent_ui/src/connection_view/elicitation_form.rs` |
| 2.10 Integrate with `ThreadView::render_elicitation_if_needed()` | Frontend | 1 day | 2.3 | `crates/agent_ui/src/connection_view/thread_view.rs` |
| 2.11 Unit tests for Form UI | Frontend | 2 days | 2.3-2.10 | `crates/agent_ui/src/connection_view/ elicitation_form_tests.rs` |

**Deliverable**: Users can interact with Form mode elicitations

### Phase 3: URL Mode UI (Week 5)

**Goals**: Implement URL mode with security features

| Task | Owner | Duration | Dependencies | File(s) Affected |
|------|-------|----------|--------------|------------------|
| 3.1 Create `ElicitationUrl` component | Frontend | 2 days | None | `crates/agent_ui/src/connection_view/elicitation_url.rs` |
| 3.2 Implement `render_security_warning()` | Frontend | 1 day | 3.1 | `crates/agent_ui/src/connection_view/elicitation_url.rs` |
| 3.3 Implement `render_url_display()` (non-clickable) | Frontend | 1 day | 3.1 | `crates/agent_ui/src/connection_view/elicitation_url.rs` |
| 3.4 Implement `render_domain_highlight()` | Frontend | 1 day | 3.1 | `crates/agent_ui/src/connection_view/elicitation_url.rs` |
| 3.5 Implement `validate_elicitation_url()` with SSRF protection | Backend | 1 day | None | `crates/acp_thread/src/url_validator.rs` |
| 3.6 Integrate with system browser (SFSafariViewController on iOS, xdg-open on Linux) | Frontend | 1 day | 3.1 | Platform-specific files |
| 3.7 Integrate with `ThreadView::render_elicitation_if_needed()` | Frontend | 1 day | 3.1 | `crates/agent_ui/src/connection_view/thread_view.rs` |
| 3.8 Implement `notifications/elicitation/complete` handler | Backend | 1 day | 3.5 | `crates/acp_thread/src/acp_thread.rs` |
| 3.9 Unit tests for URL UI | Frontend | 1 day | 3.1-3.8 | `crates/agent_ui/src/connection_view/elicitation_url_tests.rs` |
| 3.10 Security review | Security | 1 day | 3.1-3.9 | All new files |

**Deliverable**: Users can safely handle URL mode elicitations

### Phase 4: Integration & Testing (Week 6)

**Goals**: End-to-end integration and comprehensive testing

| Task | Owner | Duration | Dependencies |
|------|-------|----------|--------------|
| 4.1 Integration tests | Full Stack | 2 days | Phase 1-3 |
| 4.2 ACP compliance tests (verify `session/elicitation` method) | Full Stack | 2 days | Phase 1-3 |
| 4.3 Error handling tests (`-32042`, `-32602`) | Full Stack | 1 day | Phase 1-3 |
| 4.4 Documentation | All | 2 days | Phase 1-3 |
| 4.5 Bug fixes | All | 1 day | 4.1-4.2 |
| 4.6 Final QA | QA | 1 day | 4.5 |

**Deliverable**: Production-ready Elicitation implementation

### Dependencies

- ACP crate version supporting Elicitation (need to identify specific version)
- GPUI framework (already available)
- Existing Tool Authorization system (for reference patterns)

### Rollback Strategy

If critical issues are discovered:

1. **Feature Flag**: Wrap elicitation handling in a feature flag that can be disabled
   ```rust
   // In initialization
   if cx.has_flag("acp_elicitation_enabled") {
       capabilities.elicitation = Some(...);
   }
   ```

2. **Graceful Degradation**: If elicitation fails, return appropriate error to agent
   ```rust
   ElicitationAction::Decline  // Agent can retry or continue without
   ```

3. **Version Pinning**: Can revert to ACP crate 0.9.4 until issues are resolved

---

## Open Questions

### Technical Questions

1. **ACP Crate Version**: What is the minimum version of `agent-client-protocol` crate that supports Elicitation types?
   - Status: Investigating
   - Action: Check crate releases and changelog
   - Impact: Blocks Phase 1 start

2. **Capability Semantics**: Should `{}` (empty object) declare both modes for ACP, or only Form mode per MCP spec?
   - Note: MCP says `{}` = `{ form: {} }` for backwards compatibility
   - Recommendation: Match behavior to MCP for consistency

3. **Nested Schema Handling**: How should we handle edge cases where server sends unsupported schema structures?
   - Options: 
     a) Reject entire elicitation with error
     b) Ignore unsupported fields (silently drop)
     c) Render unsupported fields as disabled
   - Recommendation: Reject with validation error (fail fast)

4. **Browser Integration**: On Linux, should we use xdg-open or WebKit integration for URL mode?
   - Options: xdg-open (system default), WebKitWebView (embedded)
   - Recommendation: xdg-open for security (no embedding)

5. **Session Scope Validation**: Should we validate that elicitation belongs to active session once or continuously?
   - Trade-off: Performance vs. correctness
   - Recommendation: Validate once at request time (session shouldn't change during elicitation)

### Design Questions

1. **UI Layout**: Should elicitation UI appear inline in the chat or as a modal/interrupt?
   - Recommendation: Inline but prominent (similar to Tool Authorization), to maintain conversation flow
   - Alternative: Modal for URL mode (requires explicit action)

2. **Persistency**: Should incomplete elicitations persist across Zed restarts?
   - Recommendation: No - simpler, matches session lifecycle
   - Rationale: Session is transient, elicitation should be too

3. **Notification**: Should we add notification/badges for pending elicitations?
   - Recommendation: Yes, if user is in different panel
   - Implementation: Use existing notification system, badge count on agent panel

### Process Questions

1. **Code Review**: Which team members should review ACP-related changes?
   - Need to identify ACP/domain experts
   - Consider: antPB, someone from agent-servers team

2. **Testing**: Do we have access to ACP test servers for integration testing?
   - Need to check or create test fixtures
   - Consider: Creating mock ACP server for automated tests

---

## Decision Record

*This section will be filled when the RFC moves to APPROVED status*

| Field | Value |
|-------|-------|
| **Decision** | TBD |
| **Date** | TBD |
| **Approvers** | TBD |
| **Key Discussion Points** | TBD |
| **Conditions on Approval** | TBD |
| **Implementation Ticket** | TBD |

---

## Appendix A: ACP Elicitation Method Specification

### session/elicitation

**Request**:

```json
{
  "jsonrpc": "2.0",
  "id": 42,
  "method": "session/elicitation",
  "params": {
    "sessionId": "<session-id>",
    "mode": "form" | "url",
    "elicitationId": "<server-tracking-id>",  // optional
    "message": "<user-facing prompt>",
    "requestedSchema": { /* restricted JSON Schema */ },  // for form mode
    "url": "<external-url>"  // for url mode
  }
}
```

**Response**:

```json
{
  "jsonrpc": "2.0",
  "id": 42,
  "result": {
    "action": "accept" | "decline" | "cancel",
    "content": { /* form data for accept action */ }
  }
}
```

### Error Codes

| Code | Name | Description |
|------|------|-------------|
| `-32042` | URLElicitationRequiredError | URL mode elicitation required before proceeding |
| `-32602` | InvalidParams | Client doesn't support requested mode |

---

## Appendix B: Restricted JSON Schema Subset

### Supported Types

| Type | Properties | Formats |
|------|------------|---------|
| `string` | `title`, `description`, `minLength`, `maxLength`, `pattern`, `format`, `default` | `email`, `uri`, `date`, `date-time` |
| `number` | `title`, `description`, `minimum`, `maximum`, `default` | N/A |
| `integer` | `title`, `description`, `minimum`, `maximum`, `default` | N/A |
| `boolean` | `title`, `description`, `default` | N/A |
| `enum` (single) | `title`, `description`, `enum` or `oneOf` with `const`/`title`, `default` | N/A |
| `enum` (multi) | `title`, `description`, `items` with `enum` or `anyOf`, `minItems`, `maxItems`, `default` | N/A |

### Not Supported

- Nested objects
- Object arrays (enum arrays only)
- Conditional validation (`if`, `then`, `else`)
- Custom formats beyond: `email`, `uri`, `date`, `date-time`
- `additionalProperties`
- References (`$ref`)
- Compound types (`["string", "null"]`)

### Example Valid Schema

```json
{
  "type": "object",
  "properties": {
    "email": {
      "type": "string",
      "format": "email",
      "title": "Email Address",
      "description": "Your contact email"
    },
    "priority": {
      "type": "string",
      "title": "Priority Level",
      "oneOf": [
        { "const": "low", "title": "Low" },
        { "const": "medium", "title": "Medium (Recommended)" },
        { "const": "high", "title": "High" }
      ],
      "default": "medium"
    },
    "urgent": {
      "type": "boolean",
      "default": false
    },
    "tags": {
      "type": "array",
      "title": "Tags",
      "minItems": 1,
      "maxItems": 3,
      "items": {
        "type": "string",
        "enum": ["bug", "feature", "docs"]
      }
    }
  },
  "required": ["email", "priority"]
}
```

---

## Appendix C: UI Mockups

### Form Mode

```
┌─────────────────────────────────────────────────────────────────┐
│  🤖 Agent is asking for clarification                           │
│                                                                 │
│  How would you like me to approach this refactoring?           │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Refactoring Strategy *                            [▼]  │   │
│  │   Conservative - Minimal changes                          │   │
│  │   Balanced (Recommended) ← selected                       │   │
│  │   Aggressive - Maximum optimization                       │   │
│  │                                                          │   │
│  │ Email Address *                                           │   │
│  │ ┌──────────────────────────────────────────────┐         │   │
│  │ │ user@example.com                             │         │   │
│  │ └──────────────────────────────────────────────┘         │   │
│  │                                                          │   │
│  │ Priority                                                  │   │
│  │ ○ Low  ● Medium  ○ High                                  │   │
│  │                                                          │   │
│  │ ☑ Include tests                                          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  [      Submit      ]  [    Decline    ]  [     Cancel     ]   │
│                                                                 │
│  * Required fields                                              │
└─────────────────────────────────────────────────────────────────┘
```

### URL Mode

```
┌─────────────────────────────────────────────────────────────────┐
│  🔒 Secure External Authentication Required                      │
│                                                                 │
│  Please authorize access to your GitHub repositories           │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                                                          │   │
│  │  URL: https://github.com/login/oauth/authorize?client_  │   │
│  │       id=xxx&scope=repo&state=abc123                     │   │
│  │                                                          │   │
│  │  Domain: github.com ✓                                    │   │
│  │                                                          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ⚠️ This will open in your default browser                     │
│                                                                 │
│  [   Open in Browser   ]  [       Cancel       ]               │
│                                                                 │
│  This allows the agent to:                                      │
│  • Read your repositories                                       │
│  • Create pull requests on your behalf                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## Appendix D: Comparison with Tool Authorization

| Aspect | Tool Authorization | Elicitation |
|--------|-------------------|-------------|
| **Scope** | Tool call scoped | Session scoped |
| **Method** | Internal within tool flow | `session/elicitation` |
| **Options** | `PermissionOptions` (Flat/Dropdown) | JSON Schema forms |
| **Response** | Binary (Allow/Reject once/always) | Three-action (Accept/Decline/Cancel) |
| **Use case** | Permission to run tool | Clarifying questions, OAuth, config |
| **Storage** | Persists "always" decisions | No persistence |
| **State** | `ToolCallStatus::WaitingForConfirmation` | `ElicitationStatus::WaitingForUser` |
| **Pattern** | `oneshot::Sender<PermissionOptionId>` | `oneshot::Sender<ElicitationResponse>` |

---

## References

1. [ACP Elicitation Specification - RFD](https://github.com/agentclientprotocol/agent-client-protocol/blob/main/docs/rfds/elicitation.mdx)
2. [ACP Elicitation Pull Request #376](https://github.com/agentclientprotocol/agent-client-protocol/pull/376) - Merged with 33 comments
3. [ACP Session Config Options](https://github.com/agentclientprotocol/agent-client-protocol/pull/210) - Related feature using same schema constraints
4. [MCP Elicitation Spec](https://modelcontextprotocol.io/specification/draft/client/elicitation)
5. [MCP SEP-1036 URL Mode](https://modelcontextprotocol.io/community/seps/1036-url-mode-elicitation-for-secure-out-of-band-intera)
6. [Zed MCP Documentation](docs/src/ai/mcp.md)
7. [Zed Issue #37307](https://github.com/zed-industries/zed/issues/37307)
8. [JSON Schema Validation](https://json-schema.org/draft/2020-12/json-schema-validation)

---

*End of RFC-0001*

**Document Statistics**:
- Total sections: 12
- Appendices: 4
- Estimated implementation time: 6 weeks
- Lines of specification code: ~300
