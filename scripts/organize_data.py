#!/usr/bin/env python3
"""
Organize existing data files into the new standardized directory structure.

New structure:
    data/
    ├── input/              # Input documents
    │   └── documents/      # Markdown, PDF files
    ├── analysis/           # Structure analysis results
    ├── extraction/         # Enzyme extraction results
    ├── vision/             # Vision analysis results
    ├── cache/              # Cached intermediate results
    └── logs/               # Application logs
"""

import os
from pathlib import Path
import shutil
import sys

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.core.paths import get_paths


def organize_files() -> None:
    """Organize existing files into the new directory structure."""
    paths = get_paths()
    data_dir = paths.data_dir

    print("=" * 60)
    print("GPTase Data Organization Script")
    print("=" * 60)
    print(f"\nProject root: {paths.project_root}")
    print(f"Data directory: {data_dir}\n")

    # Ensure all new directories exist
    print("Creating new directory structure...")
    paths.ensure_directories()
    print("  [OK] Directory structure created\n")

    # Track moves and issues
    moves = []
    issues = []

    # 1. Move input documents
    print("1. Organizing input documents...")
    document_sources = [
        data_dir / "listov2025.md",
        data_dir / "zhang2022.md",
        data_dir / "listov2025" / "listov2025.md",
    ]

    for source in document_sources:
        if source.exists():
            # Extract document name
            doc_name = source.stem
            destination = paths.get_document_path(doc_name)

            if destination.exists():
                print(f"  [SKIP] {doc_name}.md already exists in input/documents/")
                continue

            try:
                shutil.copy2(source, destination)
                moves.append((source, destination))
                print(f"  [OK] {source} -> {destination}")
            except Exception as e:
                issues.append((source, str(e)))
                print(f"  [ERROR] Failed to copy {source}: {e}")

    # 2. Keep existing structure analysis files (already in right place)
    print("\n2. Structure analysis files...")
    analysis_files = list(paths.analysis_dir.glob("*_structure_analysis.*"))
    for f in analysis_files:
        print(f"  [OK] {f.name} (already in correct location)")

    # 3. Keep existing extraction files (already in right place)
    print("\n3. Extraction files...")
    extraction_files = list(paths.extraction_dir.glob("*_extraction.*"))
    for f in extraction_files:
        print(f"  [OK] {f.name} (already in correct location)")

    # 4. Move vision analysis files
    print("\n4. Organizing vision analysis files...")
    vision_sources = [
        data_dir / "image_analysis_results.json",
        data_dir / "image_analysis_extracted_tables.csv",
    ]

    for source in vision_sources:
        if source.exists():
            # Determine destination
            if source.suffix == ".json":
                destination = paths.get_vision_analysis_path()
            else:
                destination = paths.get_vision_tables_path()

            if destination.exists():
                print(f"  [SKIP] {source.name} already exists in vision/")
                continue

            try:
                shutil.move(str(source), str(destination))
                moves.append((source, destination))
                print(f"  [OK] {source.name} -> {destination}")
            except Exception as e:
                issues.append((source, str(e)))
                print(f"  [ERROR] Failed to move {source}: {e}")

    # 5. Remove duplicate data/data directory if it exists
    duplicate_data_dir = data_dir / "data"
    if duplicate_data_dir.exists() and duplicate_data_dir.is_dir():
        print("\n5. Removing duplicate data/data/ directory...")
        try:
            shutil.rmtree(duplicate_data_dir)
            print(f"  [OK] Removed {duplicate_data_dir}")
        except Exception as e:
            issues.append((duplicate_data_dir, str(e)))
            print(f"  [ERROR] Failed to remove {duplicate_data_dir}: {e}")

    # 6. Clean up old empty directories
    print("\n6. Cleaning up old directories...")
    old_listov_dir = data_dir / "listov2025"
    if old_listov_dir.exists() and old_listov_dir.is_dir():
        try:
            # Check if directory is empty
            if not list(old_listov_dir.iterdir()):
                shutil.rmtree(old_listov_dir)
                print(f"  [OK] Removed empty {old_listov_dir}")
            else:
                print(f"  [INFO] {old_listov_dir} not empty, keeping")
        except Exception as e:
            issues.append((old_listov_dir, str(e)))
            print(f"  [ERROR] Failed to clean {old_listov_dir}: {e}")

    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Files moved/copied: {len(moves)}")
    print(f"Issues encountered: {len(issues)}")

    if moves:
        print("\nMoved files:")
        for src, dst in moves:
            print(f"  {src} -> {dst}")

    if issues:
        print("\nIssues:")
        for src, error in issues:
            print(f"  {src}: {error}")

    print("\n" + "=" * 60)
    print("New directory structure:")
    print("=" * 60)
    print(f"""
    {data_dir}/
    ├── input/          # Input documents
    │   └── documents/
    ├── analysis/       # Structure analysis ({len(list(paths.analysis_dir.glob('*')))} files)
    ├── extraction/     # Extraction results ({len(list(paths.extraction_dir.glob('*')))} files)
    ├── vision/         # Vision analysis ({len(list(paths.vision_dir.glob('*')))} files)
    ├── cache/          # Cached results
    ├── logs/           # Application logs
    └── conversations.db
    """)

    print("\n[OK] Data organization complete!")
    print("\nNext steps:")
    print("  1. Review the organized files")
    print("  2. Test the extraction pipeline:")
    print("     python examples/reaction_extractor.py")
    print("  3. Remove old files if satisfied with the new organization")


if __name__ == "__main__":
    try:
        organize_files()
    except KeyboardInterrupt:
        print("\n\n[INFO] Organization cancelled by user")
    except Exception as e:
        print(f"\n[ERROR] Organization failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
