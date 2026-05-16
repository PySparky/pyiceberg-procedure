# pyiceberg-maintenance — Agent Instructions

Python library that generates Apache Iceberg `CALL` SQL statements from Python data structures. Zero dependencies; pure string-building logic.

## Project layout

```
src/pyiceberg_maintenance/   # library source (hatchling src-layout)
tests/                       # pytest test suite
pyproject.toml               # build, deps, pytest config
CHANGELOG.md
```

## Build & test commands

```bash
# Run tests (preferred — uses uv-managed venv)
uv run pytest

# Run tests with coverage
uv run pytest --cov=src

# Build wheel + sdist
uv build
```

> `hatch run test` / `hatch run test-cov` also work per [README.md](README.md).

## Core API (src/pyiceberg_maintenance/)

| Symbol | Purpose |
|---|---|
| `generate_iceberg_call(catalog, procedure, arguments)` | Builds a `CALL <catalog>.system.<procedure>(...)` string |
| `RawSQL(value)` | Wraps a string to be emitted verbatim (no quoting) — used for `TIMESTAMP`, `DATE`, etc. |
| `_format_sql_value(val)` | Internal recursive type dispatcher; raises `ValueError` for unsupported types |

Type mapping is documented in [README.md](README.md#type-mapping).

## Conventions

- **`bool` before `int`**: `bool` is a subclass of `int` in Python. `isinstance` checks in `_format_sql_value` must test `bool` first or it will be emitted as `1`/`0` instead of `true`/`false`.
- **`RawSQL` is the escape hatch**: never build raw SQL strings by hand — wrap them in `RawSQL`.
- **No external dependencies**: keep `dependencies = []` in `pyproject.toml`. Dev deps go in `[dependency-groups] dev`.
- **Python 3.8 compatibility**: avoid syntax or stdlib features unavailable in 3.8 (e.g. use `Dict`, `List` from `typing`; no `match` statements; no `X | Y` union syntax at runtime).
- **Tests use `_normalize_sql`** to strip insignificant whitespace before asserting output equality. Use this helper in new tests rather than hard-coding exact indentation.

## Common pitfalls

- Adding a new Python type to `_format_sql_value`? Put it **before** the `str` catch-all and **after** the `bool` guard.
- Dict keys in `map(...)` output are also recursively formatted via `_format_sql_value`, so they follow the same quoting rules as values.
