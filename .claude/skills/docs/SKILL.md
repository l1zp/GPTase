# Documentation Update

Batch update documentation for a specific feature or module.

## Instructions

When updating documentation:

1. **Read all related docs**: Use Glob to find all .md files related to the feature
2. **Compare with code**: Check if the current code matches what's documented
3. **Identify inconsistencies**: Look for outdated parameters, return types, or examples
4. **Propose structured plan**: Present a clear update plan covering all related files
5. **Execute in batch**: Update all documentation files in a focused session
6. **Verify accuracy**: If docs contain code examples, test them if possible

## Example

To update documentation for `enzyme_kinetics_extractor`:
1. Find all .md files mentioning this agent
2. Read the agent's current Markdown config
3. Check if documented capabilities match the @capabilities metadata
4. Verify parameter names and types match the tool schema
5. Update all identified inconsistencies
6. Run any example code in the docs to verify
