# Scope-Safe Refactoring

Clarify architectural scope before starting any reorganization work.

## Instructions

When user requests refactoring or reorganization:

1. **Ask for scope clarification**: "Is this change scoped to [specific domain/module] or is it a generic framework change?"
2. **Confirm understanding**: Repeat back what you understand before proceeding
3. **Identify boundaries**: Explicitly state which files/modules are in scope and which are not
4. **Check domain-specific patterns**: For enzyme-related code, use MCP tools structure. For general code, use framework patterns.

## Example

User says: "Restructure the tools"

Response:
"Before starting this refactor, I need to clarify: Is this change scoped to enzyme-specific MCP tools (src/mcp/tools/) or is it a generic framework refactor affecting core architecture? Please confirm so I can use the appropriate patterns."

This prevents building a 'generic framework' when user only wanted enzyme tool organization.
