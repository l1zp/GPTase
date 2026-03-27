# Output Paths

Use this file when the user did not provide `-o`.

## Goal

Avoid writing extraction results into an ambiguous location.

## Default Behavior

- Choose a deterministic output directory based on the source PDF name.
- Keep Markdown and extracted images in the same output directory.
- Reuse the same directory for the same input source when practical.

## Path Rules

- Quote file paths with spaces or shell-special characters.
- Prefer a directory path over a single output file path.
- If the user explicitly provides an output path, use it as-is.

## Reporting

- Tell the user where the Markdown file was written.
- Mention whether extracted images were created alongside the Markdown.
