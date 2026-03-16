---
inclusion: always
---

# Coding Standards — MANI Agentic Pattern Engine

## Python Style Rules
- Use type hints on all function signatures (parameters and return types).
- Use `typing.Protocol` for interfaces (structural subtyping), not ABCs.
- Use `@dataclass(frozen=True)` for all data models — immutability by default.
- Prefer composition and delegation over inheritance.
- Use callables over enum-based dispatch for garment-agnostic logic.
- Keep functions short and focused; extract helpers for complex logic.
- Use `from __future__ import annotations` for forward references.
- Follow PEP 8 naming: `snake_case` for functions/variables, `PascalCase` for classes.
- Maximum line length: 100 characters.
- Use f-strings for string formatting.

## Test Naming Conventions
- Test files: `tests/test_<module>.py`
- Test functions: `test_<module>_<behavior>` (e.g., `test_skirt_generator_produces_two_pieces`)
- Property tests: include a comment referencing the design property:
  ```python
  # Feature: skirt-block-pattern-grading, Property 5: Skirt Generator Output Invariants
  ```
- Property tests use `@settings(max_examples=100)` minimum.
- Use `pytest` for unit tests, `hypothesis` for property-based tests.

## Commit Message Format
- Use conventional commits: `feat:`, `fix:`, `chore:`, `test:`, `docs:`.
- Examples:
  - `feat: add SkirtGenerator with A-line block drafting`
  - `test: add bodice regression snapshot tests`
  - `chore: add coding standards steering file`
  - `fix: correct dart angle calculation for small waist-hip differential`

## Frozen Files — DO NOT MODIFY
The following files are frozen and MUST NOT be modified under any circumstances:
- `agentic_pattern_engine/sloper_generator.py`
- `agentic_pattern_engine/body_model_builder.py`
- `agentic_pattern_engine/html_visualizer.py`
- `agentic_pattern_engine/dxf_exporter.py`
- `agentic_pattern_engine/pdf_exporter.py`
- `agentic_pattern_engine/audit_trail.py`

Any garment-specific behavior from these files must be wrapped via delegation in new classes (e.g., `BodiceGarmentSpec`), never modified directly.

## PR Workflow
- After completing a PR branch, ALWAYS generate a `PR_DESCRIPTION_<branch>.md` file with:
  - What the PR does (summary)
  - Files added/modified
  - Testing section (what tests were added, test count, pass status)
  - Requirements traceability (which spec requirements are covered)
- Use the branch name (kebab-case) as the suffix, e.g., `PR_DESCRIPTION_skirt-block-pr1.md`
