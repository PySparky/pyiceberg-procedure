from datetime import datetime

from pyiceberg_maintenance import generate_iceberg_call

query = generate_iceberg_call(
    "hive_prod",
    "expire_snapshots",
    {
        "table": "db.sample",
        "older_than": datetime(2021, 6, 30, 0, 0, 0),
        "options": {"partial-progress.max-commits": 100},
    },
)

print(query)
