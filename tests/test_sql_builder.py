"""
Tests for pyiceberg_maintenance.procedure_builder.
"""

from datetime import date, datetime, timedelta, timezone

import pytest

from pyiceberg_maintenance import RawSQL, generate_iceberg_call
from pyiceberg_maintenance.procedure_builder import _format_sql_value


def _normalize_sql(sql: str) -> str:
    normalized = " ".join(sql.split()).strip()
    normalized = normalized.replace("( ", "(")
    normalized = normalized.replace(" )", ")")
    if normalized.endswith(";"):
        normalized = normalized[:-1].rstrip()
    return normalized


# ---------------------------------------------------------------------------
# _format_sql_value — unit tests per type
# ---------------------------------------------------------------------------


class TestFormatSqlValueRawSQL:
    def test_verbatim_no_quotes(self):
        assert (
            _format_sql_value(RawSQL("TIMESTAMP '2021-01-01'"))
            == "TIMESTAMP '2021-01-01'"
        )

    def test_empty_raw_sql(self):
        assert _format_sql_value(RawSQL("")) == ""


class TestFormatSqlValueBool:
    def test_true(self):
        assert _format_sql_value(True) == "true"

    def test_false(self):
        assert _format_sql_value(False) == "false"

    # bool is a subclass of int — must be checked BEFORE int
    def test_true_not_treated_as_int(self):
        assert _format_sql_value(True) != "1"


class TestFormatSqlValueNumeric:
    def test_integer(self):
        assert _format_sql_value(42) == "42"

    def test_zero(self):
        assert _format_sql_value(0) == "0"

    def test_negative_int(self):
        assert _format_sql_value(-7) == "-7"

    def test_float(self):
        assert _format_sql_value(3.14) == "3.14"

    def test_negative_float(self):
        assert _format_sql_value(-0.5) == "-0.5"


class TestFormatSqlValueDatetime:
    def test_naive_datetime(self):
        value = datetime(2021, 6, 30, 12, 34, 56, 789123)

        assert _format_sql_value(value) == ("TIMESTAMP '2021-06-30 12:34:56.789'")

    def test_naive_date(self):
        value = date(2021, 6, 30)

        assert _format_sql_value(value) == ("TIMESTAMP '2021-06-30 00:00:00.000'")

    def test_timezone_aware_datetime_is_converted_to_utc(self):
        value = datetime(
            2021,
            6,
            30,
            2,
            34,
            56,
            789123,
            tzinfo=timezone(timedelta(hours=2)),
        )

        assert _format_sql_value(value) == ("TIMESTAMP '2021-06-30 00:34:56.789'")

    def test_utc_datetime_keeps_utc_clock_time(self):
        value = datetime(2021, 6, 30, 0, 0, 0, 0, tzinfo=timezone.utc)

        assert _format_sql_value(value) == ("TIMESTAMP '2021-06-30 00:00:00.000'")


class TestFormatSqlValueString:
    def test_simple_string(self):
        assert _format_sql_value("hello") == "'hello'"

    def test_empty_string(self):
        assert _format_sql_value("") == "''"

    def test_single_quote_escaped(self):
        assert _format_sql_value("it's") == "'it''s'"

    def test_multiple_single_quotes(self):
        assert _format_sql_value("a'b'c") == "'a''b''c'"

    def test_no_double_quote_interference(self):
        assert _format_sql_value('say "hi"') == "'say \"hi\"'"


class TestFormatSqlValueNone:
    def test_none_becomes_null(self):
        assert _format_sql_value(None) == "NULL"


class TestFormatSqlValueList:
    def test_empty_list(self):
        assert _format_sql_value([]) == "array()"

    def test_int_list(self):
        assert _format_sql_value([1, 2, 3]) == "array(1, 2, 3)"

    def test_string_list(self):
        assert _format_sql_value(["a", "b"]) == "array('a', 'b')"

    def test_mixed_list(self):
        assert _format_sql_value([1, "x", None]) == "array(1, 'x', NULL)"

    def test_nested_list(self):
        assert _format_sql_value([[1, 2], [3]]) == "array(array(1, 2), array(3))"


class TestFormatSqlValueDict:
    def test_empty_dict(self):
        assert _format_sql_value({}) == "map()"

    def test_string_to_int(self):
        assert _format_sql_value({"key": 1}) == "map('key', 1)"

    def test_multiple_entries(self):
        result = _format_sql_value({"a": 1, "b": 2})
        assert _normalize_sql(result) == _normalize_sql("map('a', 1, 'b', 2)")

    def test_bool_value(self):
        assert _format_sql_value({"flag": True}) == "map('flag', true)"

    def test_nested_dict_value(self):
        result = _format_sql_value({"outer": {"inner": 42}})
        assert _normalize_sql(result) == _normalize_sql(
            "map('outer', map('inner', 42))"
        )


class TestFormatSqlValueUnsupported:
    def test_set_raises(self):
        with pytest.raises(ValueError, match="Unsupported data type"):
            _format_sql_value({1, 2})

    def test_object_raises(self):
        with pytest.raises(ValueError, match="Unsupported data type"):
            _format_sql_value(object())

    def test_bytes_raises(self):
        with pytest.raises(ValueError, match="Unsupported data type"):
            _format_sql_value(b"bytes")


# ---------------------------------------------------------------------------
# generate_iceberg_call — integration tests
# ---------------------------------------------------------------------------


class TestGenerateIcebergCall:
    def test_no_arguments(self):
        result = generate_iceberg_call("spark_catalog", "expire_snapshots", {})
        assert _normalize_sql(result) == _normalize_sql(
            "CALL spark_catalog.system.expire_snapshots();"
        )

    def test_single_string_argument(self):
        result = generate_iceberg_call(
            "spark_catalog",
            "rewrite_data_files",
            {"table": "db.sample"},
        )
        assert _normalize_sql(result) == _normalize_sql(
            "CALL spark_catalog.system.rewrite_data_files(\n    table => 'db.sample'\n);"
        )

    def test_rewrite_data_files_with_options_map(self):
        """Mirrors the first example in the module docstring."""
        result = generate_iceberg_call(
            catalog="spark_catalog",
            procedure="rewrite_data_files",
            arguments={
                "table": "db.sample",
                "options": {
                    "min-input-files": 2,
                    "remove-dangling-deletes": True,
                },
            },
        )
        expected = (
            "CALL spark_catalog.system.rewrite_data_files(\n"
            "    table => 'db.sample',\n"
            "    options => map('min-input-files', 2, 'remove-dangling-deletes', true)\n"
            ");"
        )
        assert _normalize_sql(result) == _normalize_sql(expected)

    def test_expire_snapshots_with_raw_sql_and_array(self):
        """Mirrors the second example in the module docstring."""
        result = generate_iceberg_call(
            catalog="hive_prod",
            procedure="expire_snapshots",
            arguments={
                "table": "db.sample",
                "older_than": RawSQL("TIMESTAMP '2021-06-30 00:00:00.000'"),
                "snapshot_ids": [123, 456],
            },
        )
        expected = (
            "CALL hive_prod.system.expire_snapshots(\n"
            "    table => 'db.sample',\n"
            "    older_than => TIMESTAMP '2021-06-30 00:00:00.000',\n"
            "    snapshot_ids => array(123, 456)\n"
            ");"
        )
        assert _normalize_sql(result) == _normalize_sql(expected)

    def test_null_argument(self):
        result = generate_iceberg_call("cat", "proc", {"arg": None})
        assert "arg => NULL" in result

    def test_catalog_and_procedure_appear_in_output(self):
        result = generate_iceberg_call("my_catalog", "my_proc", {"x": 1})
        assert "CALL my_catalog.system.my_proc(" in result


# ---------------------------------------------------------------------------
# Iceberg official-doc examples — all calls use named arguments
# ---------------------------------------------------------------------------


class TestSnapshotManagementProcedures:
    def test_rollback_to_snapshot(self):
        result = generate_iceberg_call(
            "catalog_name",
            "rollback_to_snapshot",
            {"table": "db.sample", "snapshot_id": 1},
        )
        assert _normalize_sql(result) == _normalize_sql(
            "CALL catalog_name.system.rollback_to_snapshot(\n"
            "    table => 'db.sample',\n"
            "    snapshot_id => 1\n"
            ");"
        )

    def test_rollback_to_timestamp(self):
        result = generate_iceberg_call(
            "catalog_name",
            "rollback_to_timestamp",
            {
                "table": "db.sample",
                "timestamp": RawSQL("TIMESTAMP '2021-06-30 00:00:00.000'"),
            },
        )
        assert _normalize_sql(result) == _normalize_sql(
            "CALL catalog_name.system.rollback_to_timestamp(\n"
            "    table => 'db.sample',\n"
            "    timestamp => TIMESTAMP '2021-06-30 00:00:00.000'\n"
            ");"
        )

    def test_set_current_snapshot_by_id(self):
        result = generate_iceberg_call(
            "catalog_name",
            "set_current_snapshot",
            {"table": "db.sample", "snapshot_id": 1},
        )
        assert _normalize_sql(result) == _normalize_sql(
            "CALL catalog_name.system.set_current_snapshot(\n"
            "    table => 'db.sample',\n"
            "    snapshot_id => 1\n"
            ");"
        )

    def test_set_current_snapshot_by_ref(self):
        result = generate_iceberg_call(
            "catalog_name",
            "set_current_snapshot",
            {"table": "db.sample", "ref": "s1"},
        )
        assert _normalize_sql(result) == _normalize_sql(
            "CALL catalog_name.system.set_current_snapshot(\n"
            "    table => 'db.sample',\n"
            "    ref => 's1'\n"
            ");"
        )

    def test_cherrypick_snapshot_positional_order(self):
        result = generate_iceberg_call(
            "catalog_name",
            "cherrypick_snapshot",
            {"table": "my_table", "snapshot_id": 1},
        )
        assert _normalize_sql(result) == _normalize_sql(
            "CALL catalog_name.system.cherrypick_snapshot(\n"
            "    table => 'my_table',\n"
            "    snapshot_id => 1\n"
            ");"
        )

    def test_cherrypick_snapshot_named_reversed_order(self):
        result = generate_iceberg_call(
            "catalog_name",
            "cherrypick_snapshot",
            {"snapshot_id": 1, "table": "my_table"},
        )
        assert _normalize_sql(result) == _normalize_sql(
            "CALL catalog_name.system.cherrypick_snapshot(\n"
            "    snapshot_id => 1,\n"
            "    table => 'my_table'\n"
            ");"
        )

    def test_publish_changes_positional_order(self):
        result = generate_iceberg_call(
            "catalog_name",
            "publish_changes",
            {"table": "my_table", "wap_id": "wap_id_1"},
        )
        assert _normalize_sql(result) == _normalize_sql(
            "CALL catalog_name.system.publish_changes(\n"
            "    table => 'my_table',\n"
            "    wap_id => 'wap_id_1'\n"
            ");"
        )

    def test_publish_changes_named_reversed_order(self):
        result = generate_iceberg_call(
            "catalog_name",
            "publish_changes",
            {"wap_id": "wap_id_2", "table": "my_table"},
        )
        assert _normalize_sql(result) == _normalize_sql(
            "CALL catalog_name.system.publish_changes(\n"
            "    wap_id => 'wap_id_2',\n"
            "    table => 'my_table'\n"
            ");"
        )

    def test_fast_forward(self):
        result = generate_iceberg_call(
            "catalog_name",
            "fast_forward",
            {"table": "my_table", "branch": "main", "to": "audit-branch"},
        )
        assert _normalize_sql(result) == _normalize_sql(
            "CALL catalog_name.system.fast_forward(\n"
            "    table => 'my_table',\n"
            "    branch => 'main',\n"
            "    to => 'audit-branch'\n"
            ");"
        )


class TestExpireSnapshotsProcedure:
    def test_older_than_with_retain_last(self):
        result = generate_iceberg_call(
            "hive_prod",
            "expire_snapshots",
            {
                "table": "db.sample",
                "older_than": RawSQL("TIMESTAMP '2021-06-30 00:00:00.000'"),
                "retain_last": 100,
            },
        )
        assert _normalize_sql(result) == _normalize_sql(
            "CALL hive_prod.system.expire_snapshots(\n"
            "    table => 'db.sample',\n"
            "    older_than => TIMESTAMP '2021-06-30 00:00:00.000',\n"
            "    retain_last => 100\n"
            ");"
        )

    def test_expire_by_snapshot_ids_array(self):
        result = generate_iceberg_call(
            "hive_prod",
            "expire_snapshots",
            {"table": "db.sample", "snapshot_ids": [123]},
        )
        assert _normalize_sql(result) == _normalize_sql(
            "CALL hive_prod.system.expire_snapshots(\n"
            "    table => 'db.sample',\n"
            "    snapshot_ids => array(123)\n"
            ");"
        )


class TestRemoveOrphanFilesProcedure:
    def test_dry_run(self):
        result = generate_iceberg_call(
            "catalog_name",
            "remove_orphan_files",
            {"table": "db.sample", "dry_run": True},
        )
        assert _normalize_sql(result) == _normalize_sql(
            "CALL catalog_name.system.remove_orphan_files(\n"
            "    table => 'db.sample',\n"
            "    dry_run => true\n"
            ");"
        )

    def test_location(self):
        result = generate_iceberg_call(
            "catalog_name",
            "remove_orphan_files",
            {"table": "db.sample", "location": "tablelocation/data"},
        )
        assert _normalize_sql(result) == _normalize_sql(
            "CALL catalog_name.system.remove_orphan_files(\n"
            "    table => 'db.sample',\n"
            "    location => 'tablelocation/data'\n"
            ");"
        )

    def test_file_list_view(self):
        result = generate_iceberg_call(
            "catalog_name",
            "remove_orphan_files",
            {"table": "db.sample", "file_list_view": "files_view"},
        )
        assert _normalize_sql(result) == _normalize_sql(
            "CALL catalog_name.system.remove_orphan_files(\n"
            "    table => 'db.sample',\n"
            "    file_list_view => 'files_view'\n"
            ");"
        )

    def test_prefix_mismatch_mode_ignore(self):
        result = generate_iceberg_call(
            "catalog_name",
            "remove_orphan_files",
            {"table": "db.sample", "prefix_mismatch_mode": "IGNORE"},
        )
        assert _normalize_sql(result) == _normalize_sql(
            "CALL catalog_name.system.remove_orphan_files(\n"
            "    table => 'db.sample',\n"
            "    prefix_mismatch_mode => 'IGNORE'\n"
            ");"
        )

    def test_prefix_mismatch_mode_delete(self):
        result = generate_iceberg_call(
            "catalog_name",
            "remove_orphan_files",
            {"table": "db.sample", "prefix_mismatch_mode": "DELETE"},
        )
        assert _normalize_sql(result) == _normalize_sql(
            "CALL catalog_name.system.remove_orphan_files(\n"
            "    table => 'db.sample',\n"
            "    prefix_mismatch_mode => 'DELETE'\n"
            ");"
        )

    def test_equal_schemes(self):
        result = generate_iceberg_call(
            "catalog_name",
            "remove_orphan_files",
            {"table": "db.sample", "equal_schemes": {"file": "file1"}},
        )
        assert _normalize_sql(result) == _normalize_sql(
            "CALL catalog_name.system.remove_orphan_files(\n"
            "    table => 'db.sample',\n"
            "    equal_schemes => map('file', 'file1')\n"
            ");"
        )

    def test_equal_authorities(self):
        result = generate_iceberg_call(
            "catalog_name",
            "remove_orphan_files",
            {"table": "db.sample", "equal_authorities": {"ns1": "ns2"}},
        )
        assert _normalize_sql(result) == _normalize_sql(
            "CALL catalog_name.system.remove_orphan_files(\n"
            "    table => 'db.sample',\n"
            "    equal_authorities => map('ns1', 'ns2')\n"
            ");"
        )

    def test_prefix_listing(self):
        result = generate_iceberg_call(
            "catalog_name",
            "remove_orphan_files",
            {"table": "db.sample", "prefix_listing": True},
        )
        assert _normalize_sql(result) == _normalize_sql(
            "CALL catalog_name.system.remove_orphan_files(\n"
            "    table => 'db.sample',\n"
            "    prefix_listing => true\n"
            ");"
        )


class TestRewriteDataFilesProcedure:
    def test_table_only(self):
        result = generate_iceberg_call(
            "catalog_name",
            "rewrite_data_files",
            {"table": "db.sample"},
        )
        assert _normalize_sql(result) == _normalize_sql(
            "CALL catalog_name.system.rewrite_data_files(\n"
            "    table => 'db.sample'\n"
            ");"
        )

    def test_sort_strategy_with_sort_order(self):
        result = generate_iceberg_call(
            "catalog_name",
            "rewrite_data_files",
            {
                "table": "db.sample",
                "strategy": "sort",
                "sort_order": "id DESC NULLS LAST,name ASC NULLS FIRST",
            },
        )
        assert _normalize_sql(result) == _normalize_sql(
            "CALL catalog_name.system.rewrite_data_files(\n"
            "    table => 'db.sample',\n"
            "    strategy => 'sort',\n"
            "    sort_order => 'id DESC NULLS LAST,name ASC NULLS FIRST'\n"
            ");"
        )

    def test_sort_strategy_with_zorder(self):
        result = generate_iceberg_call(
            "catalog_name",
            "rewrite_data_files",
            {
                "table": "db.sample",
                "strategy": "sort",
                "sort_order": "zorder(c1,c2)",
            },
        )
        assert _normalize_sql(result) == _normalize_sql(
            "CALL catalog_name.system.rewrite_data_files(\n"
            "    table => 'db.sample',\n"
            "    strategy => 'sort',\n"
            "    sort_order => 'zorder(c1,c2)'\n"
            ");"
        )

    def test_options_map(self):
        result = generate_iceberg_call(
            "catalog_name",
            "rewrite_data_files",
            {
                "table": "db.sample",
                "options": {"min-input-files": "2", "remove-dangling-deletes": "true"},
            },
        )
        assert _normalize_sql(result) == _normalize_sql(
            "CALL catalog_name.system.rewrite_data_files(\n"
            "    table => 'db.sample',\n"
            "    options => map('min-input-files', '2', 'remove-dangling-deletes', 'true')\n"
            ");"
        )

    def test_where_clause(self):
        result = generate_iceberg_call(
            "catalog_name",
            "rewrite_data_files",
            {"table": "db.sample", "where": 'id = 3 and name = "foo"'},
        )
        assert _normalize_sql(result) == _normalize_sql(
            "CALL catalog_name.system.rewrite_data_files(\n"
            "    table => 'db.sample',\n"
            "    where => 'id = 3 and name = \"foo\"'\n"
            ");"
        )


class TestRewriteManifestsProcedure:
    def test_table_only(self):
        result = generate_iceberg_call(
            "catalog_name",
            "rewrite_manifests",
            {"table": "db.sample"},
        )
        assert _normalize_sql(result) == _normalize_sql(
            "CALL catalog_name.system.rewrite_manifests(\n"
            "    table => 'db.sample'\n"
            ");"
        )

    def test_spec_id(self):
        result = generate_iceberg_call(
            "catalog_name",
            "rewrite_manifests",
            {"table": "db.sample", "spec_id": 1},
        )
        assert _normalize_sql(result) == _normalize_sql(
            "CALL catalog_name.system.rewrite_manifests(\n"
            "    table => 'db.sample',\n"
            "    spec_id => 1\n"
            ");"
        )

    def test_sort_by(self):
        result = generate_iceberg_call(
            "catalog_name",
            "rewrite_manifests",
            {"table": "db.sample", "sort_by": ["category"]},
        )
        assert _normalize_sql(result) == _normalize_sql(
            "CALL catalog_name.system.rewrite_manifests(\n"
            "    table => 'db.sample',\n"
            "    sort_by => array('category')\n"
            ");"
        )


class TestRewritePositionDeleteFilesProcedure:
    def test_table_only(self):
        result = generate_iceberg_call(
            "catalog_name",
            "rewrite_position_delete_files",
            {"table": "db.sample"},
        )
        assert _normalize_sql(result) == _normalize_sql(
            "CALL catalog_name.system.rewrite_position_delete_files(\n"
            "    table => 'db.sample'\n"
            ");"
        )

    def test_rewrite_all_option(self):
        result = generate_iceberg_call(
            "catalog_name",
            "rewrite_position_delete_files",
            {"table": "db.sample", "options": {"rewrite-all": "true"}},
        )
        assert _normalize_sql(result) == _normalize_sql(
            "CALL catalog_name.system.rewrite_position_delete_files(\n"
            "    table => 'db.sample',\n"
            "    options => map('rewrite-all', 'true')\n"
            ");"
        )

    def test_min_input_files_option(self):
        result = generate_iceberg_call(
            "catalog_name",
            "rewrite_position_delete_files",
            {"table": "db.sample", "options": {"min-input-files": "2"}},
        )
        assert _normalize_sql(result) == _normalize_sql(
            "CALL catalog_name.system.rewrite_position_delete_files(\n"
            "    table => 'db.sample',\n"
            "    options => map('min-input-files', '2')\n"
            ");"
        )


class TestTableMigrationProcedures:
    def test_snapshot_two_args(self):
        result = generate_iceberg_call(
            "catalog_name",
            "snapshot",
            {"source_table": "db.sample", "table": "db.snap"},
        )
        assert _normalize_sql(result) == _normalize_sql(
            "CALL catalog_name.system.snapshot(\n"
            "    source_table => 'db.sample',\n"
            "    table => 'db.snap'\n"
            ");"
        )

    def test_snapshot_with_location(self):
        result = generate_iceberg_call(
            "catalog_name",
            "snapshot",
            {
                "source_table": "db.sample",
                "table": "db.snap",
                "location": "/tmp/temptable/",
            },
        )
        assert _normalize_sql(result) == _normalize_sql(
            "CALL catalog_name.system.snapshot(\n"
            "    source_table => 'db.sample',\n"
            "    table => 'db.snap',\n"
            "    location => '/tmp/temptable/'\n"
            ");"
        )

    def test_migrate_with_properties(self):
        result = generate_iceberg_call(
            "catalog_name",
            "migrate",
            {"table": "spark_catalog.db.sample", "properties": {"foo": "bar"}},
        )
        assert _normalize_sql(result) == _normalize_sql(
            "CALL catalog_name.system.migrate(\n"
            "    table => 'spark_catalog.db.sample',\n"
            "    properties => map('foo', 'bar')\n"
            ");"
        )

    def test_migrate_table_only(self):
        result = generate_iceberg_call(
            "catalog_name",
            "migrate",
            {"table": "db.sample"},
        )
        assert _normalize_sql(result) == _normalize_sql(
            "CALL catalog_name.system.migrate(\n" "    table => 'db.sample'\n" ");"
        )

    def test_add_files_with_partition_filter(self):
        result = generate_iceberg_call(
            "spark_catalog",
            "add_files",
            {
                "table": "db.tbl",
                "source_table": "db.src_tbl",
                "partition_filter": {"part_col_1": "A"},
            },
        )
        assert _normalize_sql(result) == _normalize_sql(
            "CALL spark_catalog.system.add_files(\n"
            "    table => 'db.tbl',\n"
            "    source_table => 'db.src_tbl',\n"
            "    partition_filter => map('part_col_1', 'A')\n"
            ");"
        )

    def test_add_files_parquet_path(self):
        result = generate_iceberg_call(
            "spark_catalog",
            "add_files",
            {
                "table": "db.tbl",
                "source_table": "`parquet`.`path/to/table`",
            },
        )
        assert _normalize_sql(result) == _normalize_sql(
            "CALL spark_catalog.system.add_files(\n"
            "    table => 'db.tbl',\n"
            "    source_table => '`parquet`.`path/to/table`'\n"
            ");"
        )

    def test_register_table(self):
        result = generate_iceberg_call(
            "spark_catalog",
            "register_table",
            {"table": "db.tbl", "metadata_file": "path/to/metadata/file.json"},
        )
        assert _normalize_sql(result) == _normalize_sql(
            "CALL spark_catalog.system.register_table(\n"
            "    table => 'db.tbl',\n"
            "    metadata_file => 'path/to/metadata/file.json'\n"
            ");"
        )


class TestMetadataInfoProcedures:
    def test_ancestors_of_table_only(self):
        result = generate_iceberg_call(
            "spark_catalog",
            "ancestors_of",
            {"table": "db.tbl"},
        )
        assert _normalize_sql(result) == _normalize_sql(
            "CALL spark_catalog.system.ancestors_of(\n" "    table => 'db.tbl'\n" ");"
        )

    def test_ancestors_of_positional_order(self):
        result = generate_iceberg_call(
            "spark_catalog",
            "ancestors_of",
            {"table": "db.tbl", "snapshot_id": 1},
        )
        assert _normalize_sql(result) == _normalize_sql(
            "CALL spark_catalog.system.ancestors_of(\n"
            "    table => 'db.tbl',\n"
            "    snapshot_id => 1\n"
            ");"
        )

    def test_ancestors_of_named_reversed_order(self):
        result = generate_iceberg_call(
            "spark_catalog",
            "ancestors_of",
            {"snapshot_id": 1, "table": "db.tbl"},
        )
        assert _normalize_sql(result) == _normalize_sql(
            "CALL spark_catalog.system.ancestors_of(\n"
            "    snapshot_id => 1,\n"
            "    table => 'db.tbl'\n"
            ");"
        )


class TestChangeDataCaptureProcedures:
    def test_create_changelog_view_by_snapshot_range(self):
        result = generate_iceberg_call(
            "spark_catalog",
            "create_changelog_view",
            {
                "table": "db.tbl",
                "options": {"start-snapshot-id": "1", "end-snapshot-id": "2"},
            },
        )
        assert _normalize_sql(result) == _normalize_sql(
            "CALL spark_catalog.system.create_changelog_view(\n"
            "    table => 'db.tbl',\n"
            "    options => map('start-snapshot-id', '1', 'end-snapshot-id', '2')\n"
            ");"
        )

    def test_create_changelog_view_by_timestamp_range_with_view_name(self):
        result = generate_iceberg_call(
            "spark_catalog",
            "create_changelog_view",
            {
                "table": "db.tbl",
                "options": {
                    "start-timestamp": "1678335750489",
                    "end-timestamp": "1678992105265",
                },
                "changelog_view": "my_changelog_view",
            },
        )
        assert _normalize_sql(result) == _normalize_sql(
            "CALL spark_catalog.system.create_changelog_view(\n"
            "    table => 'db.tbl',\n"
            "    options => map('start-timestamp', '1678335750489', 'end-timestamp', '1678992105265'),\n"
            "    changelog_view => 'my_changelog_view'\n"
            ");"
        )

    def test_create_changelog_view_with_identifier_columns(self):
        result = generate_iceberg_call(
            "spark_catalog",
            "create_changelog_view",
            {
                "table": "db.tbl",
                "options": {"start-snapshot-id": "1", "end-snapshot-id": "2"},
                "identifier_columns": ["id", "name"],
            },
        )
        assert _normalize_sql(result) == _normalize_sql(
            "CALL spark_catalog.system.create_changelog_view(\n"
            "    table => 'db.tbl',\n"
            "    options => map('start-snapshot-id', '1', 'end-snapshot-id', '2'),\n"
            "    identifier_columns => array('id', 'name')\n"
            ");"
        )

    def test_create_changelog_view_net_changes(self):
        result = generate_iceberg_call(
            "spark_catalog",
            "create_changelog_view",
            {
                "table": "db.tbl",
                "options": {"end-snapshot-id": "87647489814522183702"},
                "net_changes": True,
            },
        )
        assert _normalize_sql(result) == _normalize_sql(
            "CALL spark_catalog.system.create_changelog_view(\n"
            "    table => 'db.tbl',\n"
            "    options => map('end-snapshot-id', '87647489814522183702'),\n"
            "    net_changes => true\n"
            ");"
        )


class TestTableAndPartitionStatsProcedures:
    def test_compute_table_stats_table_only(self):
        result = generate_iceberg_call(
            "catalog_name",
            "compute_table_stats",
            {"table": "my_table"},
        )
        assert _normalize_sql(result) == _normalize_sql(
            "CALL catalog_name.system.compute_table_stats(\n"
            "    table => 'my_table'\n"
            ");"
        )

    def test_compute_table_stats_with_snapshot_id(self):
        result = generate_iceberg_call(
            "catalog_name",
            "compute_table_stats",
            {"table": "my_table", "snapshot_id": "snap1"},
        )
        assert _normalize_sql(result) == _normalize_sql(
            "CALL catalog_name.system.compute_table_stats(\n"
            "    table => 'my_table',\n"
            "    snapshot_id => 'snap1'\n"
            ");"
        )

    def test_compute_table_stats_with_columns(self):
        result = generate_iceberg_call(
            "catalog_name",
            "compute_table_stats",
            {"table": "my_table", "snapshot_id": "snap1", "columns": ["col1", "col2"]},
        )
        assert _normalize_sql(result) == _normalize_sql(
            "CALL catalog_name.system.compute_table_stats(\n"
            "    table => 'my_table',\n"
            "    snapshot_id => 'snap1',\n"
            "    columns => array('col1', 'col2')\n"
            ");"
        )

    def test_compute_partition_stats_table_only(self):
        result = generate_iceberg_call(
            "catalog_name",
            "compute_partition_stats",
            {"table": "my_table"},
        )
        assert _normalize_sql(result) == _normalize_sql(
            "CALL catalog_name.system.compute_partition_stats(\n"
            "    table => 'my_table'\n"
            ");"
        )

    def test_compute_partition_stats_with_snapshot_id(self):
        result = generate_iceberg_call(
            "catalog_name",
            "compute_partition_stats",
            {"table": "my_table", "snapshot_id": "snap1"},
        )
        assert _normalize_sql(result) == _normalize_sql(
            "CALL catalog_name.system.compute_partition_stats(\n"
            "    table => 'my_table',\n"
            "    snapshot_id => 'snap1'\n"
            ");"
        )


class TestRewriteTablePathProcedure:
    def test_full_rewrite(self):
        result = generate_iceberg_call(
            "catalog_name",
            "rewrite_table_path",
            {
                "table": "db.my_table",
                "source_prefix": "hdfs://nn:8020/path/to/source_table",
                "target_prefix": "s3a://bucket/prefix/db.db/my_table",
            },
        )
        assert _normalize_sql(result) == _normalize_sql(
            "CALL catalog_name.system.rewrite_table_path(\n"
            "    table => 'db.my_table',\n"
            "    source_prefix => 'hdfs://nn:8020/path/to/source_table',\n"
            "    target_prefix => 's3a://bucket/prefix/db.db/my_table'\n"
            ");"
        )

    def test_incremental_rewrite_with_all_args(self):
        result = generate_iceberg_call(
            "catalog_name",
            "rewrite_table_path",
            {
                "table": "db.my_table",
                "source_prefix": "s3a://bucketOne/prefix/db.db/my_table",
                "target_prefix": "s3a://bucketTwo/prefix/db.db/my_table",
                "start_version": "v2.metadata.json",
                "end_version": "v20.metadata.json",
                "staging_location": "s3a://bucketStaging/my_table",
            },
        )
        assert _normalize_sql(result) == _normalize_sql(
            "CALL catalog_name.system.rewrite_table_path(\n"
            "    table => 'db.my_table',\n"
            "    source_prefix => 's3a://bucketOne/prefix/db.db/my_table',\n"
            "    target_prefix => 's3a://bucketTwo/prefix/db.db/my_table',\n"
            "    start_version => 'v2.metadata.json',\n"
            "    end_version => 'v20.metadata.json',\n"
            "    staging_location => 's3a://bucketStaging/my_table'\n"
            ");"
        )
