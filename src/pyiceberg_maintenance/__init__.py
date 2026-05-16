"""
pyiceberg_maintenance
~~~~~~~~~~~~~~~~~~~~~

Utilities for generating Apache Iceberg maintenance SQL (``CALL``) statements
from Python data structures.

Public API
----------
- :class:`RawSQL`              – wrap a literal SQL expression to skip quoting
- :func:`generate_iceberg_call` – build a ``CALL`` statement
  SQL statement
"""

from pyiceberg_maintenance.procedure_builder import (
    RawSQL,
    generate_iceberg_call,
)

__all__ = ["RawSQL", "generate_iceberg_call"]
