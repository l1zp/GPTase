#!/usr/bin/env python3
"""
Migrate existing flat output structure to document-based output structure.

OLD STRUCTURE:
    data/
    ├── analysis/
    │   ├── listov2025_structure_analysis.json
    │   └── zhang2022_structure_analysis.json
    ├── extraction/
    │   ├── listov2025_extraction.json
    │   └── zhang2022_extraction.json
    └── vision/
        ├── vision_analysis_results.json
        └── extracted_tables.csv

NEW STRUCTURE:
    data/
    └── output/
        ├── listov2025/
        │   ├── analysis/
        │   │   ├── structure_analysis.json
        │   │   └── structure_analysis_images.csv
        │   ├── extraction/
        │   │   ├── extraction.json
        │   │   └── extraction.csv
        │   └── vision/
        │       ├── vision_analysis.json
        │       └── extracted_tables.csv
        └── zhang2022/
            ├── analysis/
            │   └── structure_analysis.json
            └── extraction/
                └── extraction.json
"""

import os
from pathlib import Path
import re
import shutil
import sys

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.core.paths import get_paths


def extract_document_name(filename: str) -> str:
    """Extract document name from filename.

    Examples:
        listov2025_structure_analysis.json -> listov2025
        zhang2022_extraction.json -> zhang2022
        vision_analysis_results.json -> None (no document)
    """
    # Match patterns: {doc}_structure_analysis.json, {doc}_extraction.json, etc.
    match = re.match(
        r'^([a-zA-Z0-9_]+)_(?:structure_analysis|extraction|vision_analysis|extracted_tables)',
        filename)
    if match:
        return match.group(1)
    return None


def migrate_files() -> None:
    """Migrate files from old flat structure to new document-based structure."""
    paths = get_paths()
    data_dir = paths.data_dir

    print("=" * 70)
    print("GPTase File Migration Script")
    print("Migrating to document-based output structure")
    print("=" * 70)
    print(f"\nProject root: {paths.project_root}")
    print(f"Data directory: {data_dir}\n")

    # Track migrations
    migrations = []
    errors = []

    # 1. Migrate analysis files
    print("1. Migrating analysis files...")
    old_analysis_dir = data_dir / "analysis"
    if old_analysis_dir.exists():
        for file in old_analysis_dir.glob("*_structure_analysis.*"):
            doc_name = extract_document_name(file.name)
            if doc_name:
                # Determine new path
                if file.suffix == ".json":
                    new_path = paths.get_structure_analysis_path(doc_name)
                elif file.suffix == ".csv":
                    if "images" in file.name:
                        new_path = paths.get_structure_analysis_images_csv_path(
                            doc_name)
                    else:
                        new_path = paths.get_structure_analysis_csv_path(doc_name)
                else:
                    continue

                # Skip if already exists
                if new_path.exists():
                    print(f"  [SKIP] {file.name} -> already exists at new location")
                    continue

                try:
                    new_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(file, new_path)
                    migrations.append((file, new_path))
                    print(f"  [OK] {file.name} -> {new_path.relative_to(data_dir)}")
                except Exception as e:
                    errors.append((file, str(e)))
                    print(f"  [ERROR] Failed to migrate {file.name}: {e}")

    # 2. Migrate extraction files
    print("\n2. Migrating extraction files...")
    old_extraction_dir = data_dir / "extraction"
    if old_extraction_dir.exists():
        for file in old_extraction_dir.glob("*"):
            if file.is_file():
                doc_name = extract_document_name(file.name)
                if not doc_name:
                    # Try to handle special files (combined_data.csv, enzyme_to_pdb.csv, etc.)
                    # These will be copied to a generic location
                    doc_name = "_shared"

                # Determine new path
                if "extraction.json" in file.name:
                    new_path = paths.get_extraction_path(doc_name)
                elif "extraction.csv" in file.name:
                    new_path = paths.get_extraction_csv_path(doc_name)
                elif file.name in [
                        "combined_data.csv", "enzyme_to_pdb.csv", "pdb_info.csv"
                ]:
                    # Keep these in a shared location
                    shared_dir = paths.output_dir / "_shared" / "extraction"
                    shared_dir.mkdir(parents=True, exist_ok=True)
                    new_path = shared_dir / file.name
                else:
                    # Unknown file type, skip
                    continue

                # Skip if already exists
                if new_path.exists():
                    print(f"  [SKIP] {file.name} -> already exists at new location")
                    continue

                try:
                    new_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(file, new_path)
                    migrations.append((file, new_path))
                    print(f"  [OK] {file.name} -> {new_path.relative_to(data_dir)}")
                except Exception as e:
                    errors.append((file, str(e)))
                    print(f"  [ERROR] Failed to migrate {file.name}: {e}")

    # 3. Migrate vision files
    print("\n3. Migrating vision files...")
    old_vision_dir = data_dir / "vision"
    if old_vision_dir.exists():
        for file in old_vision_dir.glob("*"):
            if file.is_file():
                # Vision files might be generic or document-specific
                doc_name = extract_document_name(file.name)
                if not doc_name:
                    # Generic vision files - assign to listov2025 by default (most common)
                    # or keep in output root
                    if "vision_analysis" in file.name:
                        new_path = paths.get_vision_analysis_path()
                    elif "extracted_tables" in file.name:
                        new_path = paths.get_vision_tables_path()
                    else:
                        # Skip unknown files
                        continue
                else:
                    # Document-specific vision files
                    if "vision_analysis" in file.name:
                        new_path = paths.get_vision_analysis_path(doc_name)
                    elif "extracted_tables" in file.name:
                        new_path = paths.get_vision_tables_path(doc_name)
                    else:
                        continue

                # Skip if already exists
                if new_path.exists():
                    print(f"  [SKIP] {file.name} -> already exists at new location")
                    continue

                try:
                    new_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(file, new_path)
                    migrations.append((file, new_path))
                    print(f"  [OK] {file.name} -> {new_path.relative_to(data_dir)}")
                except Exception as e:
                    errors.append((file, str(e)))
                    print(f"  [ERROR] Failed to migrate {file.name}: {e}")

    # Summary
    print("\n" + "=" * 70)
    print("Migration Summary")
    print("=" * 70)
    print(f"Files migrated: {len(migrations)}")
    print(f"Errors: {len(errors)}")

    if migrations:
        print(f"\nFirst 5 migrations:")
        for src, dst in migrations[:5]:
            print(f"  {src.name} -> {dst.relative_to(data_dir)}")
        if len(migrations) > 5:
            print(f"  ... and {len(migrations) - 5} more")

    if errors:
        print(f"\nErrors:")
        for src, error in errors:
            print(f"  {src.name}: {error}")

    # Show new structure
    print("\n" + "=" * 70)
    print("New Output Structure")
    print("=" * 70)

    output_dir = paths.output_dir
    if output_dir.exists():
        for doc_dir in sorted(output_dir.iterdir()):
            if doc_dir.is_dir() and not doc_dir.name.startswith("_"):
                print(f"\n{doc_dir.name}/")
                for subdir in sorted(doc_dir.iterdir()):
                    if subdir.is_dir():
                        file_count = len(list(subdir.glob("*")))
                        print(f"  ├── {subdir.name}/ ({file_count} files)")

    print("\n" + "=" * 70)
    print("Migration complete!")
    print("=" * 70)
    print("\nNext steps:")
    print("  1. Verify the migrated files are correct")
    print("  2. Test extraction pipeline:")
    print("     python examples/reaction_extractor.py")
    print("  3. If satisfied, remove old directories:")
    print("     rm -rf data/analysis data/extraction data/vision")
    print("\nNote: Old files are preserved. Review before deleting.")


if __name__ == "__main__":
    try:
        migrate_files()
    except KeyboardInterrupt:
        print("\n\n[INFO] Migration cancelled by user")
    except Exception as e:
        print(f"\n[ERROR] Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
