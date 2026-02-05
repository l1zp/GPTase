# Dead Code Removal

Safety-first workflow for removing unused code from the codebase.

## Instructions

When removing dead code, follow this verification pattern:

1. **Search for references**: Use Grep to find all imports, exports, and usages across the entire codebase
2. **Check dependencies**: Identify any code that depends on the target code
3. **Review tests**: Find and mark any tests that reference this code
4. **Present findings**: Show user what you found before making any changes
5. **Execute safely**: Only remove after user confirms it's safe
6. **Verify**: Run tests after removal to ensure nothing broke

## Example

To remove a function or class:
1. Grep for its name across all Python files
2. Check if it's exported in `__init__.py` or referenced in config files
3. List any test files that import or use it
4. Ask user: "Found X references. Safe to proceed?"
5. After confirmation, remove the code
6. Run `pytest tests/` to verify
