# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-05-15

### Added
- `RawSQL` wrapper class to inject verbatim SQL expressions without quoting.
- `generate_iceberg_call()` function to build Apache Iceberg `CALL` statements
  from Python dictionaries, with named argument syntax.
- Internal `_format_sql_value()` helper supporting `bool`, `int`, `float`,
  `str`, `list`, `dict`, `None`, and `RawSQL` types.
- Full pytest test suite covering all type branches and end-to-end call generation.
