#!/usr/bin/env python3
"""
Validate Markdown reports produced by the deep-research skill.

The validator is intentionally aligned with the current skill contract:
- Markdown report
- explicit multi-round research process
- evidence-backed findings
- counterevidence / uncertainty handling
- traceable source list
"""

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Dict, List

REQUIRED_SECTIONS = [
    "Executive Summary",
    "Research Question and Scope",
    "Research Process",
    "Key Findings",
    "Counterevidence and Uncertainties",
    "Conclusion or Recommendation",
    "Sources",
]

PLACEHOLDERS = [
    "TBD",
    "TODO",
    "FIXME",
    "[citation needed]",
    "[needs citation]",
]

TRUNCATION_PATTERNS = [
    r"Content continues",
    r"Due to length",
    r"would continue",
    r"\[Sections \d+-\d+",
    r"Additional sections",
]


class ReportValidator:

    def __init__(self, report_path: Path):
        self.report_path = report_path
        self.content = report_path.read_text(encoding="utf-8")
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def validate(self) -> bool:
        checks = [
            self._check_required_sections,
            self._check_research_process,
            self._check_citations,
            self._check_sources_section,
            self._check_placeholders,
            self._check_truncation,
            self._check_internal_links,
        ]

        for check in checks:
            check()

        return not self.errors

    def _check_required_sections(self) -> None:
        missing = []
        for section in REQUIRED_SECTIONS:
            if not re.search(rf"^##\s+{re.escape(section)}\s*$", self.content,
                             re.MULTILINE | re.IGNORECASE):
                missing.append(section)

        if missing:
            self.errors.append(f"Missing required sections: {', '.join(missing)}")

    def _check_research_process(self) -> None:
        section = self._extract_section("Research Process")
        if not section:
            return

        rounds = re.findall(r"^###\s+Round\s+\d+", section,
                            re.MULTILINE | re.IGNORECASE)
        if len(rounds) < 2:
            self.errors.append(
                "Research Process must document at least two rounds (e.g. Round 1, Round 2)"
            )

        lowered = section.lower()
        if "gap" not in lowered and "conflict" not in lowered:
            self.warnings.append(
                "Research Process does not explicitly mention gaps or conflicts that drove follow-up research"
            )

    def _check_citations(self) -> None:
        citations = re.findall(r"\[(\d+)\]", self.content)
        if not citations:
            self.errors.append("No citations found in report")
            return

        unique = sorted({int(value) for value in citations})
        if len(unique) < 5:
            self.warnings.append(
                f"Only {len(unique)} unique citations found; deep research is usually stronger with broader support"
            )

    def _check_sources_section(self) -> None:
        section = self._extract_section("Sources")
        if not section:
            return

        entries = re.findall(r"^\[(\d+)\]\s+.+$", section, re.MULTILINE)
        if not entries:
            self.errors.append("Sources section has no numbered entries")
            return

        text_citations = {
            int(value)
            for value in re.findall(r"\[(\d+)\]", self.content)
        }
        source_entries = {int(value) for value in entries}

        missing = sorted(text_citations - source_entries)
        if missing:
            self.errors.append(f"Citations missing from Sources section: {missing}")

        unused = sorted(source_entries - text_citations)
        if unused:
            self.warnings.append(f"Unused entries in Sources section: {unused}")

    def _check_placeholders(self) -> None:
        found = [token for token in PLACEHOLDERS if token in self.content]
        if found:
            self.errors.append(f"Found placeholder text: {', '.join(found)}")

    def _check_truncation(self) -> None:
        for pattern in TRUNCATION_PATTERNS:
            if re.search(pattern, self.content, re.IGNORECASE):
                self.errors.append(f"Detected truncation pattern: {pattern}")
                return

    def _check_internal_links(self) -> None:
        internal_links = re.findall(r"\[.*?\]\((\.\/.*?)\)", self.content)
        broken = []
        for link in internal_links:
            link_path = link.split("#")[0]
            full_path = self.report_path.parent / link_path
            if not full_path.exists():
                broken.append(link)
        if broken:
            self.errors.append(f"Broken internal links: {', '.join(broken)}")

    def _extract_section(self, heading: str) -> str:
        pattern = rf"^##\s+{re.escape(heading)}\s*$([\s\S]*?)(?=^##\s+|\Z)"
        match = re.search(pattern, self.content, re.MULTILINE | re.IGNORECASE)
        return match.group(1).strip() if match else ""

    def to_json(self) -> Dict:
        return {
            "report_path": str(self.report_path),
            "errors": self.errors,
            "warnings": self.warnings,
            "passed": not self.errors,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
        }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate deep-research Markdown report")
    parser.add_argument("--report", "-r", required=True, help="Path to report file")
    parser.add_argument("--json", action="store_true", help="Print JSON result")
    args = parser.parse_args()

    report_path = Path(args.report)
    if not report_path.exists():
        print(f"[ERROR] Report file not found: {report_path}")
        sys.exit(1)

    validator = ReportValidator(report_path)
    passed = validator.validate()

    if args.json:
        print(json.dumps(validator.to_json(), indent=2))
    else:
        if validator.errors:
            print("VALIDATION FAILED")
            for error in validator.errors:
                print(f"- {error}")
        else:
            print("VALIDATION PASSED")

        if validator.warnings:
            print("WARNINGS")
            for warning in validator.warnings:
                print(f"- {warning}")

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
