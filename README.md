# pyiceberg-maintenance

Python utilities for generating Apache Iceberg maintenance `CALL` statements
from plain Python data structures — no string templating required.

## Installation

```bash
pip install pyiceberg-maintenance
pip install git+https://github.com/PySparky/pyiceberg-procedure.git
```

## Quick start

```python
from pyiceberg_maintenance import RawSQL, generate_iceberg_call

# 1. rewrite_data_files with options map
print(generate_iceberg_call(
    catalog="spark_catalog",
    procedure="rewrite_data_files",
    arguments={
        "table": "db.sample",
        "options": {
            "min-input-files": 2,
            "remove-dangling-deletes": True,
        },
    },
))
# CALL spark_catalog.system.rewrite_data_files(
#     table => 'db.sample',
#     options => map('min-input-files', 2, 'remove-dangling-deletes', true)
# );

# 2. expire_snapshots with a raw TIMESTAMP expression and an id array
print(generate_iceberg_call(
    catalog="hive_prod",
    procedure="expire_snapshots",
    arguments={
        "table": "db.sample",
        "older_than": RawSQL("TIMESTAMP '2021-06-30 00:00:00.000'"),
        "snapshot_ids": [123, 456],
    },
))
# CALL hive_prod.system.expire_snapshots(
#     table => 'db.sample',
#     older_than => TIMESTAMP '2021-06-30 00:00:00.000',
#     snapshot_ids => array(123, 456)
# );
```

## API

### `generate_iceberg_call(catalog, procedure, arguments) -> str`

| Parameter   | Type              | Description                                      |
|-------------|-------------------|--------------------------------------------------|
| `catalog`   | `str`             | Spark catalog name, e.g. `"spark_catalog"`       |
| `procedure` | `str`             | Iceberg system procedure, e.g. `"rewrite_data_files"` |
| `arguments` | `dict[str, Any]`  | Named arguments; values are auto-converted       |

### `RawSQL(value: str)`

Wrap any string in `RawSQL(...)` to have it emitted verbatim — useful for
`TIMESTAMP`, `DATE`, and other SQL literals that must not be single-quoted by
the library.

### Type mapping

| Python type | SQL output              |
|-------------|-------------------------|
| `RawSQL`    | verbatim string         |
| `bool`      | `true` / `false`        |
| `int/float` | numeric literal         |
| `str`       | `'...'` (quotes escaped)|
| `list`      | `array(item, ...)`      |
| `dict`      | `map(k, v, ...)`        |
| `None`      | `NULL`                  |

## Development

```bash
# Install Hatch
pip install hatch

# Run tests
hatch run test

# Run tests with coverage
hatch run test-cov

# Build wheel + sdist
hatch build
```

## License

MIT
