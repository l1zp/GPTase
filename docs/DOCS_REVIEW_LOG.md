# Documentation Review Log

This log records Markdown files that were reviewed, optimized, moved, or excluded, with justifications.

## Moved and Optimized

- `README.md` → `docs/README.md`
  - Optimizations: clarified installation (including editable install), unified `GPTase.*` imports, added configuration via template JSON and environment variables, updated usage examples, and testing instructions.
  - Link updates: adjusted LICENSE link to `../LICENSE` to reflect new location.
  - Rationale: Core project overview and usage guide; valuable and up-to-date.

- `MCP_GUIDE.md` → `docs/MCP_GUIDE.md`
  - Optimizations: standardized dependency install (`requirements.txt`), updated `PYTHONPATH` examples for macOS/Windows, minor clarity fixes.
  - Rationale: Relevant for MCP users integrating with Claude Desktop; kept references to `src.mcp.server` which match current project layout.

- `START_FRONTEND.md` → `docs/START_FRONTEND.md`
  - Optimizations: corrected uvicorn command to `src.web.app:create_app`, standardized troubleshooting commands, improved clarity and consistency.
  - Rationale: Useful quick-start for the web frontend; updated to match current code locations.

## Excluded (Not moved)

- `REFACTORING_COMPLETE.md`
  - Reason: Historical summary; contains outdated commands (e.g., `test_structure.py`) and duplicates information now present in the main README.

- `CLEANUP_SUMMARY.md`
  - Reason: Historical cleanup notes; redundant with current README and not user-facing documentation.

- `.trae/documents/Implement Enzyme Design Extraction Agent.md` and `.trae/documents/Refactor Agents And Provide Agent Demo.md`
  - Reason: Internal development notes specific to the IDE session; not intended for end-user documentation and may drift from the current codebase.

- `.pytest_cache/README.md`
  - Reason: Auto-generated cache metadata; not part of user documentation.

## Link Verification

- Internal paths updated where necessary (e.g., LICENSE relative link in `docs/README.md`).
- External links retained; formatting checked (HTTP/HTTPS). For runtime validation, use link checkers in CI if desired.

## Consistency and Style

- Headings and sections normalized to English and consistent tone.
- Code blocks use bash or python as appropriate.
- Instructions prefer `PYTHONPATH="$(pwd)"` for macOS shell examples.

