#!/usr/bin/env python
"""Self-healing documentation system.

Scans Python files for docstring/signature mismatches and fixes them.
Also validates code examples in documentation.

Usage:
    python scripts/self_healing_docs.py [--dry-run] [--validate-examples]
"""

import argparse
import ast
import inspect
import logging
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class DocstringSignatureMismatch:
    """Represents a mismatch between docstring and function signature."""

    def __init__(
        self,
        file_path: str,
        function_name: str,
        line_number: int,
        mismatch_type: str,
        details: str,
        actual_params: List[str],
        documented_params: List[str],
    ):
        self.file_path = file_path
        self.function_name = function_name
        self.line_number = line_number
        self.mismatch_type = mismatch_type
        self.details = details
        self.actual_params = actual_params
        self.documented_params = documented_params

    def __repr__(self) -> str:
        return (f"DocstringSignatureMismatch({self.file_path}:{self.line_number}, "
                f"{self.function_name}, {self.mismatch_type})")


class DocstringAnalyzer:
    """Analyzes Python files for docstring/signature mismatches."""

    # Patterns to extract Args sections from docstrings
    ARGS_PATTERN = re.compile(
        r"Args:\s*\n((?:\s+\w+.*\n?)+)",
        re.MULTILINE,
    )
    PARAM_LINE_PATTERN = re.compile(
        r"^\s+(\w+):\s*",
        re.MULTILINE,
    )

    # Exception names to ignore when found in docstrings (these are from Raises sections)
    KNOWN_EXCEPTIONS = {
        "SOPExecutionError",
        "SOPNotFoundError",
        "SOPValidationError",
        "AgentDispatchError",
        "AgentInitializationError",
        "ConfigurationError",
        "ValueError",
        "Structure",  # This is likely a type annotation, not a parameter
        "NotImplementedError",
        "StreamChunk",  # From Yields sections
        "ImportError",
        "RuntimeError",
    }

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.mismatches: List[DocstringSignatureMismatch] = []

    def scan_directory(self, directory: Path) -> List[DocstringSignatureMismatch]:
        """Scan all Python files in a directory for mismatches."""
        for py_file in directory.rglob("*.py"):
            # Skip test files and __init__.py for now
            if "test_" in str(py_file) or py_file.name == "__init__.py":
                continue
            self.scan_file(py_file)

        return self.mismatches

    def scan_file(self, file_path: Path) -> List[DocstringSignatureMismatch]:
        """Scan a single Python file for docstring/signature mismatches."""
        try:
            source = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except SyntaxError as e:
            logger.warning(f"Syntax error in {file_path}: {e}")
            return []

        file_mismatches = []

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                mismatch = self._check_function(file_path, node, source)
                if mismatch:
                    file_mismatches.append(mismatch)
                    self.mismatches.append(mismatch)

        return file_mismatches

    def _check_function(
        self,
        file_path: Path,
        node: ast.FunctionDef,
        source: str,
    ) -> Optional[DocstringSignatureMismatch]:
        """Check a single function for docstring/signature mismatch."""
        # Get docstring
        docstring = ast.get_docstring(node)
        if not docstring:
            return None

        # Get actual parameters
        actual_params = self._extract_signature_params(node)

        # Get documented parameters
        documented_params = self._extract_docstring_params(docstring)

        # Compare
        actual_set = set(actual_params)
        documented_set = set(documented_params)

        # Check for missing params in docstring
        missing_in_docs = actual_set - documented_set
        # Check for extra params in docstring (removed from signature)
        # Filter out known exception names (from Raises sections)
        extra_in_docs = documented_set - actual_set
        extra_in_docs = extra_in_docs - self.KNOWN_EXCEPTIONS

        if missing_in_docs or extra_in_docs:
            mismatch_type = []
            details = []

            if missing_in_docs:
                mismatch_type.append("missing_params")
                details.append(f"Missing in docstring: {sorted(missing_in_docs)}")
            if extra_in_docs:
                mismatch_type.append("extra_params")
                details.append(f"Extra in docstring: {sorted(extra_in_docs)}")

            return DocstringSignatureMismatch(
                file_path=str(file_path),
                function_name=node.name,
                line_number=node.lineno,
                mismatch_type=", ".join(mismatch_type),
                details="; ".join(details),
                actual_params=actual_params,
                documented_params=documented_params,
            )

        return None

    def _extract_signature_params(self, node: ast.FunctionDef) -> List[str]:
        """Extract parameter names from function signature.

        Skips `self` and `cls` parameters as they are typically not documented.
        """
        params = []

        # Regular arguments (skip self/cls)
        for i, arg in enumerate(node.args.args):
            # Skip self (first arg in instance methods) and cls (first arg in classmethods)
            if i == 0 and arg.arg in ("self", "cls"):
                continue
            params.append(arg.arg)

        # Keyword-only arguments
        for arg in node.args.kwonlyargs:
            params.append(arg.arg)

        # *args
        if node.args.vararg:
            params.append(f"*{node.args.vararg.arg}")

        # **kwargs
        if node.args.kwarg:
            params.append(f"**{node.args.kwarg.arg}")

        return params

    def _extract_docstring_params(self, docstring: str) -> List[str]:
        """Extract parameter names from docstring Args section."""
        params = []

        # Find Args section
        match = self.ARGS_PATTERN.search(docstring)
        if not match:
            return params

        args_section = match.group(1)

        # Extract parameter names
        for line in args_section.split("\n"):
            param_match = self.PARAM_LINE_PATTERN.match(line)
            if param_match:
                param_name = param_match.group(1)
                # Skip type annotations in param name
                if ":" not in param_name:
                    params.append(param_name)

        return params


class DocstringFixer:
    """Fixes docstring/signature mismatches."""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.fixed_count = 0

    def fix_mismatches(
        self,
        mismatches: List[DocstringSignatureMismatch],
    ) -> int:
        """Fix all detected mismatches."""
        # Group by file
        by_file: Dict[str, List[DocstringSignatureMismatch]] = {}
        for mismatch in mismatches:
            if mismatch.file_path not in by_file:
                by_file[mismatch.file_path] = []
            by_file[mismatch.file_path].append(mismatch)

        # Fix each file
        for file_path, file_mismatches in by_file.items():
            self._fix_file(file_path, file_mismatches)

        return self.fixed_count

    def _fix_file(
        self,
        file_path: str,
        mismatches: List[DocstringSignatureMismatch],
    ) -> None:
        """Fix mismatches in a single file."""
        try:
            source = Path(file_path).read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to read {file_path}: {e}")
            return

        lines = source.split("\n")

        # Sort mismatches by line number (descending) to avoid offset issues
        mismatches.sort(key=lambda m: m.line_number, reverse=True)

        for mismatch in mismatches:
            new_lines = self._fix_function_docstring(
                lines,
                mismatch,
            )
            if new_lines:
                lines = new_lines
                self.fixed_count += 1

        if not self.dry_run:
            Path(file_path).write_text("\n".join(lines), encoding="utf-8")
            logger.info(f"[OK] Fixed {len(mismatches)} mismatches in {file_path}")
        else:
            logger.info(
                f"[DRY-RUN] Would fix {len(mismatches)} mismatches in {file_path}")

    def _fix_function_docstring(
        self,
        lines: List[str],
        mismatch: DocstringSignatureMismatch,
    ) -> Optional[List[str]]:
        """Fix a single function's docstring."""
        # Find the docstring
        func_line = mismatch.line_number - 1  # 0-indexed

        # Look for docstring start (usually next line after function def)
        docstring_start = None
        docstring_end = None

        for i in range(func_line + 1, min(func_line + 10, len(lines))):
            line = lines[i].strip()
            if line.startswith('"""') or line.startswith("'''"):
                quote = '"""' if line.startswith('"""') else "'''"
                docstring_start = i

                # Check if docstring ends on same line
                if line.count(quote) >= 2 and len(line) > 6:
                    docstring_end = i
                else:
                    # Find end
                    for j in range(i + 1, len(lines)):
                        if quote in lines[j]:
                            docstring_end = j
                            break
                break

        if docstring_start is None or docstring_end is None:
            logger.warning(f"Could not find docstring for {mismatch.function_name} "
                           f"at line {mismatch.line_number}")
            return None

        # Extract existing docstring
        docstring_lines = lines[docstring_start:docstring_end + 1]
        docstring = self._extract_docstring_text(docstring_lines)

        # Fix the docstring
        fixed_docstring = self._update_args_section(
            docstring,
            mismatch.actual_params,
        )

        if fixed_docstring == docstring:
            return None

        # Reconstruct the file
        quote = '"""'
        new_docstring_lines = [f'{quote}{fixed_docstring}{quote}']
        if docstring_end > docstring_start:
            # Multi-line docstring
            new_docstring_lines = [quote] + fixed_docstring.split("\n") + [quote]

        return (lines[:docstring_start] + new_docstring_lines
                + lines[docstring_end + 1:])

    def _extract_docstring_text(self, docstring_lines: List[str]) -> str:
        """Extract the text content from docstring lines."""
        if not docstring_lines:
            return ""

        # Remove quote markers
        text = "\n".join(docstring_lines)
        text = text.strip('"\'')

        return text.strip()

    def _update_args_section(
        self,
        docstring: str,
        actual_params: List[str],
    ) -> str:
        """Update the Args section of a docstring."""
        # Find Args section
        args_match = re.search(
            r"(Args:\s*\n)((?:\s+\w+.*\n?)+)",
            docstring,
            re.MULTILINE,
        )

        if not args_match:
            # No Args section, add one
            return docstring.rstrip() + "\n\nArgs:\n" + "\n".join(
                f"    {param}: Description." for param in actual_params)

        # Extract existing param descriptions
        existing_params: Dict[str, str] = {}
        args_content = args_match.group(2)

        for line in args_content.split("\n"):
            match = re.match(r"\s+(\w+):\s*(.*)", line)
            if match:
                param_name = match.group(1)
                description = match.group(2)
                existing_params[param_name] = description

        # Build new Args section
        new_args_lines = ["Args:"]
        for param in actual_params:
            if param in existing_params:
                new_args_lines.append(f"    {param}: {existing_params[param]}")
            else:
                new_args_lines.append(f"    {param}: Description.")

        new_args = "\n".join(new_args_lines)

        # Replace old Args section
        return docstring[:args_match.start()] + new_args + docstring[args_match.end():]


class CLIValidator:
    """Validates and updates README.md with CLI changes."""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run

    def update_readme(self, readme_path: Path, main_module: Path) -> bool:
        """Update README.md with CLI changes from argparse definitions."""
        try:
            # Import the main module to get argparse config
            import importlib.util
            spec = importlib.util.spec_from_file_location("main", main_module)
            if not spec or not spec.loader:
                logger.error(f"Could not load module: {main_module}")
                return False

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Find parse_args function
            if not hasattr(module, "parse_args"):
                logger.warning("No parse_args function found in main module")
                return False

            # Get parser
            parser = self._extract_parser(module)
            if not parser:
                logger.warning("Could not extract argparse parser")
                return False

            # Generate CLI documentation
            cli_docs = self._generate_cli_docs(parser)

            # Read current README
            readme_content = readme_path.read_text(encoding="utf-8")

            # Check if update is needed
            if self._needs_update(readme_content, cli_docs):
                if not self.dry_run:
                    self._update_cli_section(readme_path, readme_content, cli_docs)
                    logger.info(f"[OK] Updated CLI documentation in {readme_path}")
                else:
                    logger.info(
                        f"[DRY-RUN] Would update CLI documentation in {readme_path}")
                return True

            logger.info("CLI documentation is up to date")
            return False

        except Exception as e:
            logger.error(f"Failed to update README: {e}")
            return False

    def _extract_parser(self, module) -> Optional[Any]:
        """Extract argparse parser from module."""
        try:
            # Call parse_args with --help to get parser
            import argparse
            parser = argparse.ArgumentParser()

            # Look for subparsers in the module
            for name in dir(module):
                obj = getattr(module, name)
                if isinstance(obj, argparse.ArgumentParser):
                    return obj

            return None
        except Exception:
            return None

    def _generate_cli_docs(self, parser) -> str:
        """Generate CLI documentation from parser."""
        from contextlib import redirect_stdout
        import io

        # Capture help output
        f = io.StringIO()
        try:
            with redirect_stdout(f):
                parser.print_help()
        except SystemExit:
            pass

        return f.getvalue()

    def _needs_update(self, readme_content: str, cli_docs: str) -> bool:
        """Check if README needs updating."""
        # Simple check - look for Usage section
        if "Usage" not in readme_content:
            return True

        # Check if main commands are documented
        commands = ["gptase agent", "gptase list", "gptase sop"]
        for cmd in commands:
            if cmd not in readme_content:
                return True

        return False

    def _update_cli_section(
        self,
        readme_path: Path,
        readme_content: str,
        cli_docs: str,
    ) -> None:
        """Update the CLI section in README."""
        # Find the Basic Usage section
        usage_match = re.search(
            r"## Basic Usage\n(.*?)(?=\n##|\Z)",
            readme_content,
            re.DOTALL,
        )

        if usage_match:
            # Replace existing usage section
            new_section = f"## Basic Usage\n\n```bash\n{cli_docs}```\n"
            updated = (readme_content[:usage_match.start()] + new_section
                       + readme_content[usage_match.end():])
        else:
            # Add new usage section after Quick Start
            new_section = f"\n## Basic Usage\n\n```bash\n{cli_docs}```\n"
            updated = readme_content + new_section

        readme_path.write_text(updated, encoding="utf-8")


class CodeExampleValidator:
    """Validates code examples in documentation."""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.errors: List[Tuple[str, str]] = []

    def validate_directory(self, directory: Path) -> bool:
        """Validate all code examples in markdown files."""
        all_valid = True

        for md_file in directory.rglob("*.md"):
            if not self._validate_file(md_file):
                all_valid = False

        return all_valid

    def _validate_file(self, md_file: Path) -> bool:
        """Validate code examples in a single markdown file."""
        content = md_file.read_text(encoding="utf-8")

        # Extract Python code blocks
        code_blocks = re.findall(
            r"```python\n(.*?)\n```",
            content,
            re.DOTALL,
        )

        all_valid = True

        for i, code in enumerate(code_blocks, 1):
            if not self._validate_code_block(code, md_file, i):
                all_valid = False

        return all_valid

    def _validate_code_block(
        self,
        code: str,
        md_file: Path,
        block_num: int,
    ) -> bool:
        """Validate a single code block.

        Documentation code blocks often contain snippets that show
        async usage patterns (with await) that are meant to be used
        inside async functions. We wrap these in an async function
        to validate the syntax.
        """
        try:
            # Try to compile the code as-is first
            compile(code, f"{md_file}:{block_num}", "exec")
            logger.debug(f"[OK] Code block {block_num} in {md_file} is valid")
            return True
        except SyntaxError as e:
            # If the error is 'await outside function', wrap in async function
            if "'await' outside" in str(e):
                try:
                    # Indent each line and wrap in async function
                    indented_code = "\n".join("    " + line if line.strip() else line
                                              for line in code.split("\n"))
                    wrapped_code = f"async def _doc_example():\n{indented_code}"
                    compile(wrapped_code, f"{md_file}:{block_num}", "exec")
                    logger.debug(f"[OK] Code block {block_num} in {md_file} is valid "
                                 f"(async snippet)")
                    return True
                except SyntaxError:
                    # Still failed - report original error
                    pass

            error_msg = f"Syntax error in code block {block_num} in {md_file}: {e}"
            self.errors.append((str(md_file), error_msg))
            logger.error(f"[ERROR] {error_msg}")
            return False


def main() -> int:
    """Run the self-healing documentation system."""
    parser = argparse.ArgumentParser(description="Self-healing documentation system")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without making changes",
    )
    parser.add_argument(
        "--validate-examples",
        action="store_true",
        help="Validate code examples in documentation",
    )
    parser.add_argument(
        "--directory",
        type=Path,
        default=Path("gptase"),
        help="Directory to scan (default: gptase)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    print("=" * 60)
    print("Self-Healing Documentation System")
    print("=" * 60)

    # Step 1: Scan for docstring/signature mismatches
    print("\n[1/4] Scanning for docstring/signature mismatches...")
    analyzer = DocstringAnalyzer(dry_run=args.dry_run)
    mismatches = analyzer.scan_directory(args.directory)

    if mismatches:
        print(f"\n[INFO] Found {len(mismatches)} docstring/signature mismatches:")
        for m in mismatches:
            print(f"  - {m.file_path}:{m.line_number} - {m.function_name}")
            print(f"    {m.details}")
    else:
        print("[OK] No docstring/signature mismatches found")

    # Step 2: Fix mismatches
    print("\n[2/4] Fixing docstring/signature mismatches...")
    if mismatches:
        fixer = DocstringFixer(dry_run=args.dry_run)
        fixed = fixer.fix_mismatches(mismatches)
        print(f"[OK] Fixed {fixed} mismatches")
    else:
        print("[OK] No fixes needed")

    # Step 3: Update README with CLI changes
    print("\n[3/4] Checking CLI documentation in README.md...")
    readme_path = Path("README.md")
    main_module = Path("gptase/main.py")

    if readme_path.exists() and main_module.exists():
        validator = CLIValidator(dry_run=args.dry_run)
        validator.update_readme(readme_path, main_module)
    else:
        print("[WARNING] README.md or gptase/main.py not found")

    # Step 4: Validate code examples
    print("\n[4/4] Validating code examples in documentation...")
    if args.validate_examples:
        example_validator = CodeExampleValidator(dry_run=args.dry_run)
        if example_validator.validate_directory(Path(".")):
            print("[OK] All code examples are valid")
        else:
            print(
                f"[ERROR] Found {len(example_validator.errors)} invalid code examples")
            for file_path, error in example_validator.errors:
                print(f"  - {file_path}: {error}")
    else:
        print("[INFO] Skipping code example validation (use --validate-examples)")

    print("\n" + "=" * 60)
    print("Documentation self-healing complete")
    print("=" * 60)

    return 0 if not mismatches else 1


if __name__ == "__main__":
    sys.exit(main())
