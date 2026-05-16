from __future__ import annotations

import datetime as dt
from typing import Any, Dict


class RawSQL:
    """
    A wrapper to inject raw SQL expressions (e.g. ``TIMESTAMP '...'``, zorder
    expressions) that bypass standard string-quoting so they appear verbatim
    in the generated statement.

    Example::

        RawSQL("TIMESTAMP '2021-06-30 00:00:00.000'")
    """

    def __init__(self, value: str) -> None:
        self.value = value

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"RawSQL({self.value!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, RawSQL):
            return self.value == other.value
        return NotImplemented


def _format_sql_value(val: Any) -> str:
    """
    Map a Python value to its Spark SQL string representation.

    Supported types
    ---------------
    - :class:`RawSQL`   → verbatim string (no quoting)
    - :class:`bool`     → ``true`` / ``false``
    - :class:`int`      → numeric literal
    - :class:`float`    → numeric literal
    - :class:`datetime.date` / :class:`datetime.datetime`
                        → ``TIMESTAMP 'YYYY-MM-DD HH:MM:SS.mmm'``
    - :class:`list`     → ``array(item, ...)``
    - :class:`dict`     → ``map(k, v, ...)``
    - :class:`str`      → ``'...'`` (internal single-quotes are doubled)
    - ``None``          → ``NULL``

    Raises
    ------
    ValueError
        If *val* is of an unsupported type.
    """
    if isinstance(val, RawSQL):
        return str(val)
    if isinstance(val, dt.datetime):
        timestamp_value = val.astimezone(dt.timezone.utc) if val.tzinfo else val
        formatted = timestamp_value.strftime("%Y-%m-%d %H:%M:%S")
        milliseconds = timestamp_value.microsecond // 1000
        return str(RawSQL(f"TIMESTAMP '{formatted}.{milliseconds:03d}'"))
    if isinstance(val, dt.date):
        return str(RawSQL(f"TIMESTAMP '{val:%Y-%m-%d} 00:00:00.000'"))
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, list):
        formatted_items = [_format_sql_value(item) for item in val]
        return f"array({', '.join(formatted_items)})"
    if isinstance(val, dict):
        map_args: list[str] = []
        for k, v in val.items():
            map_args.append(_format_sql_value(k))
            map_args.append(_format_sql_value(v))
        return f"map({', '.join(map_args)})"
    if isinstance(val, str):
        escaped = val.replace("'", "''")
        return f"'{escaped}'"
    if val is None:
        return "NULL"
    raise ValueError(f"Unsupported data type for Iceberg CALL command: {type(val)}")


def generate_iceberg_call(
    catalog: str,
    procedure: str,
    arguments: Dict[str, Any],
) -> str:
    """
    Generate an Apache Iceberg ``CALL`` statement with named arguments.

    Parameters
    ----------
    catalog:
        Spark catalog name (e.g. ``"spark_catalog"`` or ``"hive_prod"``).
    procedure:
        Iceberg system procedure name (e.g. ``"rewrite_data_files"``).
    arguments:
        Mapping of argument name → value.  Values are converted to their
        Spark SQL representations by :func:`_format_sql_value`.

    Returns
    -------
    str
        A complete one-line ``CALL`` statement.

    Example::

        >>> generate_iceberg_call(
        ...     catalog="spark_catalog",
        ...     procedure="rewrite_data_files",
        ...     arguments={"table": "db.sample"},
        ... )
        "CALL spark_catalog.system.rewrite_data_files(table => 'db.sample')"
    """
    if not arguments:
        return f"CALL {catalog}.system.{procedure}()"

    args_list = [
        f"{key} => {_format_sql_value(value)}" for key, value in arguments.items()
    ]
    args_str = ", ".join(args_list)
    return f"CALL {catalog}.system.{procedure}({args_str})"
