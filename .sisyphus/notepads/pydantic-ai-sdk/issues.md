### [2025-01-21] Task 9: Implement SkillRegistry & Anthropic Loader

**Issue**: Subagent reported completion but verification failed.
- Claimed: `skills.py` created with implementations
- Actual: File does not exist on disk
- Root cause: Test file created but implementation file never materialized
**Resolution Needed**: Re-delegate Task 9 with stronger verification constraint
**Dependencies**: Requires AgentConfig, FlowConfig (from Task 6) - these are DONE
