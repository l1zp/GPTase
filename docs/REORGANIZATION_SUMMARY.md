# Data Directory Reorganization Summary

**Date**: 2025-01-31
**Status**: Completed

## Overview

This document summarizes the reorganization of the GPTase `data/` directory to establish a standardized, maintainable file structure with centralized path management.

## Changes Made

### 1. New Centralized Path Management (`src/core/paths.py`)

Created a new `ProjectPaths` class that provides a single source of truth for all file paths:
- Auto-detects project root
- Provides standardized methods for getting file paths
- Ensures consistent directory structure across the framework
- Automatically creates required directories

**Key Methods**:
- `get_document_path(doc_name)` - Input document paths
- `get_structure_analysis_path(doc_name)` - Phase 1 analysis results
- `get_extraction_path(doc_name)` - Phase 2 extraction results
- `get_vision_analysis_path(doc_name)` - Vision analysis results
- `resolve_input_path(path)` - Resolve user-provided input paths
- `resolve_output_path(path)` - Resolve user-provided output paths

### 2. New Directory Structure

```
data/
├── input/              # NEW: Centralized input directory
│   └── documents/      # NEW: Source documents (markdown, pdf)
├── analysis/           # EXISTING: Phase 1 structure analysis
├── extraction/         # EXISTING: Phase 2 enzyme extraction
├── vision/             # NEW: Vision analysis results
├── cache/              # NEW: Cached intermediate results
├── logs/               # NEW: Application logs
└── conversations.db    # EXISTING: Session tracking database
```

### 3. Code Updates

Updated the following files to use the new `ProjectPaths` system:

1. **`src/tools/document_structure_analyzer.py`**
   - Updated `save_document_analysis()` to use `ProjectPaths`
   - Now supports optional `output_dir` parameter with fallback to centralized paths

2. **`examples/reaction_extractor.py`**
   - Updated to use `get_paths()` for all file operations
   - Default input path: `data/input/documents/listov2025.md`
   - Default output path: `data/extraction/{doc}_extraction.json`

3. **`examples/vision_image_analyzer.py`**
   - Updated to use `get_paths()` for all file operations
   - Vision analysis outputs now go to `data/vision/`
   - Default CSV path: `data/analysis/{doc}_structure_analysis_images.csv`

### 4. File Organization

**Moved Files**:
- `data/listov2025.md` → `data/input/documents/listov2025.md`
- `data/zhang2022.md` → `data/input/documents/zhang2022.md`
- `data/image_analysis_results.json` → `data/vision/vision_analysis_results.json`
- `data/image_analysis_extracted_tables.csv` → `data/vision/extracted_tables.csv`

**Removed**:
- Duplicate `data/data/` directory

**Kept Unchanged** (already in correct location):
- All `data/analysis/*` files
- All `data/extraction/*` files
- `data/conversations.db`
- `data/listov2025/` (contains images, backward compatibility)

### 5. New Documentation

1. **`data/README.md`**
   - Comprehensive documentation of the new directory structure
   - Usage examples and best practices
   - Workflow descriptions
   - Maintenance guidelines

2. **`data/.gitignore`**
   - Ignores cache and log files
   - Keeps input documents and database
   - Optional: Can ignore large JSON/CSV files

3. **`scripts/organize_data.py`**
   - Automated script for organizing files into new structure
   - Can be run multiple times safely
   - Provides detailed summary of changes

## Benefits

### 1. Consistency
- All file paths managed through one central class
- No more hardcoded paths scattered across codebase
- Consistent naming conventions

### 2. Maintainability
- Easy to change directory structure in one place
- Clear separation of concerns (input, analysis, extraction, vision)
- Self-documenting code through method names

### 3. Scalability
- Easy to add new file types
- Supports multiple documents without confusion
- Cache and log directories ready for production use

### 4. Developer Experience
- Clear expectations for where files go
- Auto-creation of directories
- Easy to find specific file types

## Migration Guide

### For Users

**Before**:
```bash
# Old way - documents scattered in data/
python examples/reaction_extractor.py -i data/listov2025.md
```

**After**:
```bash
# New way - organized structure
python examples/reaction_extractor.py -i listov2025.md  # Auto-resolves to data/input/documents/
python examples/reaction_extractor.py  # Uses default listov2025.md
```

### For Developers

**Before**:
```python
# Old way - hardcoded paths
data_dir = Path(__file__).parent.parent / "data"
input_file = data_dir / "listov2025.md"
output_file = data_dir / "extraction" / f"{doc}_extraction.json"
output_file.parent.mkdir(exist_ok=True)
```

**After**:
```python
# New way - centralized paths
paths = get_paths()
input_file = paths.get_document_path("listov2025")
output_file = paths.get_extraction_path("listov2025")
# Directories auto-created by paths.ensure_directories()
```

## Backward Compatibility

- Old file locations still work (existing files not deleted)
- Scripts support both relative and absolute paths
- `listov2025/` directory preserved for image references
- Database path unchanged (`data/conversations.db`)

## Testing

To verify the reorganization:

```bash
# 1. Check directory structure
ls -la data/

# 2. Test extraction with new paths
python examples/reaction_extractor.py

# 3. Verify output locations
ls -la data/extraction/
ls -la data/analysis/

# 4. Test vision analyzer
python examples/vision_image_analyzer.py

# 5. Verify vision outputs
ls -la data/vision/
```

## Future Improvements

1. **Configuration-based paths**: Allow users to customize directory locations via config file
2. **Path validation**: Add checks for file existence and permissions
3. **Migration utilities**: More sophisticated tools for migrating old projects
4. **Path aliases**: Support shortcuts for common paths
5. **Multi-project support**: Support multiple data directories for different projects

## Related Files

- `src/core/paths.py` - Core path management implementation
- `data/README.md` - User-facing directory documentation
- `scripts/organize_data.py` - Organization automation script
- `data/.gitignore` - Git ignore patterns for data directory

## Conclusion

The reorganization establishes a clean, scalable foundation for the GPTase framework's data management. All new development should use the `ProjectPaths` class for file operations to maintain consistency.

For questions or issues, refer to:
- `data/README.md` for directory usage
- `src/core/paths.py` for API documentation
- `scripts/organize_data.py` for reorganizing files
