"""CSV analysis tools powered by DuckDB.

These tools load tabular data into the shared data store so the agent can
inspect, describe, and query CSV files across multiple turns.
"""
from __future__ import annotations

import csv
import hashlib
import os
from contextlib import closing
from datetime import datetime
from decimal import Decimal
from typing import Any, Iterable, Sequence

import duckdb
from langchain.tools import tool, ToolRuntime
from langchain_core.messages import ToolMessage
from langgraph.types import Command

from ..langchain_state import DataEntry, HyperfocusContext, HyperfocusState, data_exists, retrieve_data

MAX_PREVIEW_ROWS = 5
MAX_QUERY_DISPLAY_ROWS = 20
MAX_STORED_QUERY_ROWS = 1000


@tool
def load_csv_file(
    file_path: str,
    runtime: ToolRuntime[HyperfocusContext, HyperfocusState],
) -> Command:
    """Load a CSV from disk, store it for later steps, and show a quick preview."""

    try:
        abs_path = _normalize_path(file_path)
        if not os.path.isfile(abs_path):
            return _error_command(runtime, f"Error: '{abs_path}' is not a file.")

        file_size = os.path.getsize(abs_path)
        dialect, has_header = _detect_csv_format(abs_path)

        schema = _describe_csv(abs_path, dialect, has_header)
        column_names = [column["name"] for column in schema]
        row_count = _count_rows(abs_path, dialect, has_header)
        preview_rows = _preview_rows(
            abs_path, dialect, has_header, limit=MAX_PREVIEW_ROWS
        )

        fingerprint = _fingerprint_path(abs_path)
        data_id = f"csv_{fingerprint}"

        metadata = {
            "path": abs_path,
            "rows": row_count,
            "columns": len(schema),
            "column_names": column_names,
            "file_size_bytes": file_size,
            "delimiter": dialect.get("delimiter"),
            "quotechar": dialect.get("quotechar"),
            "has_header": has_header,
            "sample_rows": preview_rows,
        }

        entry: DataEntry = {
            "data_id": data_id,
            "data_type": "csv_table",
            "content": {
                "path": abs_path,
                "has_header": has_header,
                "dialect": dialect,
            },
            "created_at": datetime.now().isoformat(),
            "metadata": metadata,
        }

        preview_text = _format_table(column_names, preview_rows)

        message = (
            "✓ Loaded CSV file\n"
            f"Table: {data_id}"
            f"Path: {abs_path}\n"
            f"Data ID: {data_id}\n"
            f"Rows: {row_count:,}\n"
            f"Columns ({len(column_names)}): {', '.join(column_names)}\n\n"
            "Preview (first rows):\n"
            f"{preview_text}\n\n"
            "You can now call describe_csv_table(data_id=...) or "
            "query_csv_sql(data_id=..., sql='SELECT * FROM {data_id} ...')."
        )

        return Command(
            update={
                "stored_data": entry,
                "messages": [
                    ToolMessage(content=message, tool_call_id=runtime.tool_call_id)
                ],
            }
        )

    except duckdb.Error as err:
        return _error_command(runtime, f"Error reading CSV with DuckDB: {err}")
    except Exception as err:  # pragma: no cover - defensive catch
        return _error_command(runtime, f"Error loading CSV: {err}")


@tool
def describe_csv_table(
    data_id: str, runtime: ToolRuntime[HyperfocusContext, HyperfocusState]
) -> str:
    """Show DuckDB's inferred schema for a previously loaded CSV."""

    if not data_exists(runtime, data_id):
        return f"Error: No CSV found with ID '{data_id}'. Use load_csv_file first."

    data = retrieve_data(runtime, data_id)
    if not isinstance(data, dict) or "path" not in data:
        return f"Error: Stored data '{data_id}' is not a CSV description."

    entry = data["content"]

    abs_path = entry["path"]
    dialect = entry.get("dialect", {})
    has_header = entry.get("has_header", True)

    try:
        schema = _describe_csv(abs_path, dialect, has_header)
        row_count = _count_rows(abs_path, dialect, has_header)

        schema_lines = [
            f"- {column['name']} ({column['type']})" for column in schema
        ]

        return (
            "✓ CSV schema\n"
            f"Path: {abs_path}\n"
            f"Rows: {row_count:,}\n"
            f"Columns ({len(schema)}):\n" + "\n".join(schema_lines)
        )

    except duckdb.Error as err:
        return f"Error describing CSV: {err}"
    except Exception as err:  # pragma: no cover - defensive catch
        return f"Error describing CSV: {err}"


@tool
def query_csv_sql(
    data_id: str,
    sql: str,
    runtime: ToolRuntime[HyperfocusContext, HyperfocusState],
) -> Command:
    """Execute a DuckDB SQL statement against the stored CSV."""

    if not data_exists(runtime, data_id):
        return _error_command(runtime, f"Error: No CSV found with ID '{data_id}'.")

    data = retrieve_data(runtime, data_id)
    if not isinstance(data, dict) or "path" not in data:
        return _error_command(runtime, f"Error: Stored data '{data_id}' is not a CSV table.")

    entry = data["content"]

    abs_path = entry["path"]
    dialect = entry.get("dialect", {})
    has_header = entry.get("has_header", True)

    sanitized_sql = sql.strip().rstrip(";")
    if not sanitized_sql:
        return _error_command(runtime, "Error: SQL query is empty.")

    try:
        with closing(duckdb.connect(database=":memory:")) as conn:
            _register_csv_view(conn, abs_path, dialect, has_header, table_name=data_id)

            relation = conn.sql(sanitized_sql)
            columns = list(relation.columns)
            rows = relation.fetchall()
            row_count = _count_relation_rows(conn, sanitized_sql)

        preview_rows = rows[:MAX_QUERY_DISPLAY_ROWS]
        preview_text = _format_table(columns, preview_rows)

        stored_rows = rows[:MAX_STORED_QUERY_ROWS]
        result_records = _rows_to_dicts(columns, stored_rows)

        result_hash = hashlib.md5((data_id + sanitized_sql).encode()).hexdigest()[:8]
        result_data_id = f"csv_query_{result_hash}"

        metadata = {
            "source_data_id": data_id,
            "sql": sanitized_sql,
            "row_count": row_count,
            "columns": columns,
            "stored_rows": len(result_records),
        }

        result_entry: DataEntry = {
            "data_id": result_data_id,
            "data_type": "csv_query_result",
            "content": {"columns": columns, "rows": result_records},
            "created_at": datetime.now().isoformat(),
            "metadata": metadata,
        }

        message = (
            "✓ Query executed\n"
            f"Source ID: {data_id}\n"
            f"Result ID: {result_data_id}\n"
            f"Rows returned: {row_count:,}\n"
            f"Columns: {', '.join(columns)}\n\n"
            f"Preview (up to {MAX_QUERY_DISPLAY_ROWS} rows):\n{preview_text}\n\n"
            "This does not return the full results. Use run_task_on_stored_row_data(data_id=..., prompt=...) to process results in a subagent."
        )

        return Command(
            update={
                "stored_data": result_entry,
                "messages": [
                    ToolMessage(content=message, tool_call_id=runtime.tool_call_id)
                ],
            }
        )

    except duckdb.Error as err:
        return _error_command(runtime, f"Error executing SQL: {err}")
    except Exception as err:  # pragma: no cover - defensive catch
        return _error_command(runtime, f"Error executing SQL: {err}")

def _register_csv_view(
    conn: duckdb.DuckDBPyConnection,
    abs_path: str,
    dialect: dict[str, str | None],
    has_header: bool,
    table_name: str,
) -> None:
    read_call = _build_read_csv_call(abs_path, dialect, has_header)
    conn.execute(f"CREATE OR REPLACE VIEW {table_name} AS SELECT * FROM {read_call}")


def _describe_csv(
    abs_path: str,
    dialect: dict[str, str | None],
    has_header: bool,
) -> list[dict[str, str]]:
    with closing(duckdb.connect(database=":memory:")) as conn:
        read_call = _build_read_csv_call(abs_path, dialect, has_header)
        rows = conn.execute(f"DESCRIBE SELECT * FROM {read_call}").fetchall()

    schema: list[dict[str, str]] = []
    for name, dtype, *_ in rows:
        schema.append({"name": name, "type": dtype})
    return schema


def _count_rows(
    abs_path: str,
    dialect: dict[str, str | None],
    has_header: bool,
) -> int:
    with closing(duckdb.connect(database=":memory:")) as conn:
        read_call = _build_read_csv_call(abs_path, dialect, has_header)
        result = conn.execute(f"SELECT COUNT(*) FROM {read_call}").fetchone()
    return int(result[0]) if result else 0


def _preview_rows(
    abs_path: str,
    dialect: dict[str, str | None],
    has_header: bool,
    limit: int,
) -> list[list[Any]]:
    with closing(duckdb.connect(database=":memory:")) as conn:
        read_call = _build_read_csv_call(abs_path, dialect, has_header)
        rows = conn.execute(
            f"SELECT * FROM {read_call} LIMIT {limit}"
        ).fetchall()
    return [list(row) for row in rows]


def _count_relation_rows(conn: duckdb.DuckDBPyConnection, sql: str) -> int:
    wrapped = f"SELECT COUNT(*) FROM ({sql}) AS __hf_subquery"
    result = conn.execute(wrapped).fetchone()
    return int(result[0]) if result else 0


def _format_table(columns: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    if not columns:
        return "(no columns)"

    display_rows = rows[:MAX_QUERY_DISPLAY_ROWS]
    formatted_rows: list[list[str]] = []
    for row in display_rows:
        formatted_row: list[str] = []
        for idx in range(len(columns)):
            value = row[idx] if idx < len(row) else None
            formatted_row.append(_format_value(value))
        formatted_rows.append(formatted_row)

    widths = [len(column) for column in columns]
    for formatted_row in formatted_rows:
        for idx, cell in enumerate(formatted_row):
            widths[idx] = max(widths[idx], len(cell))

    header = " | ".join(
        columns[idx].ljust(widths[idx]) for idx in range(len(columns))
    )
    separator = "-+-".join("-" * width for width in widths)

    if not formatted_rows:
        body_lines = ["(no rows)"]
    else:
        body_lines = [
            " | ".join(row[idx].ljust(widths[idx]) for idx in range(len(columns)))
            for row in formatted_rows
        ]
        if len(rows) > len(display_rows):
            body_lines.append(
                f"... {len(rows) - len(display_rows)} more row(s) not shown"
            )

    return "\n".join([header, separator, *body_lines])


def _format_value(value: Any) -> str:
    normalized = _normalize_value(value)
    if normalized is None:
        return "NULL"
    if isinstance(normalized, bool):
        return "TRUE" if normalized else "FALSE"
    return str(normalized)


def _rows_to_dicts(
    columns: Sequence[str], rows: Iterable[Sequence[Any]]
) -> list[dict[str, Any]]:
    dict_rows: list[dict[str, Any]] = []
    for row in rows:
        record: dict[str, Any] = {}
        for idx, column in enumerate(columns):
            value = row[idx] if idx < len(row) else None
            record[column] = _normalize_value(value)
        dict_rows.append(record)
    return dict_rows


def _normalize_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:  # pragma: no cover - best effort
            return str(value)
    return str(value)


def _normalize_path(file_path: str) -> str:
    return os.path.abspath(os.path.expanduser(file_path))


def _build_read_csv_call(
    abs_path: str,
    dialect: dict[str, str | None],
    has_header: bool,
) -> str:
    escaped_path = abs_path.replace("'", "''")
    options: list[str] = [
        f"HEADER={'TRUE' if has_header else 'FALSE'}",
        "SAMPLE_SIZE=-1",
        "ALL_VARCHAR=TRUE",
        "IGNORE_ERRORS=TRUE",
        "NULL_PADDING=TRUE",
        "STRICT_MODE=FALSE",
    ]

    delimiter = dialect.get("delimiter") if dialect else None
    if delimiter:
        escaped_delim = delimiter.replace("'", "''")
        options.append(f"DELIM='{escaped_delim}'")

    quotechar = dialect.get("quotechar") if dialect else None
    if quotechar:
        escaped_quote = quotechar.replace("'", "''")
        options.append(f"QUOTE='{escaped_quote}'")
        options.append(f"ESCAPE='{escaped_quote}'")

    options_sql = ", ".join(options)
    return f"read_csv_auto('{escaped_path}', {options_sql})"


def _detect_csv_format(abs_path: str) -> tuple[dict[str, str | None], bool]:
    try:
        with open(abs_path, "r", encoding="utf-8", errors="replace") as handle:
            sample = handle.read(32768)
            if not sample:
                return {"delimiter": ",", "quotechar": '"'}, True
            sniffer = csv.Sniffer()
            dialect_obj = sniffer.sniff(sample)
            has_header = sniffer.has_header(sample)
            return (
                {
                    "delimiter": getattr(dialect_obj, "delimiter", ","),
                    "quotechar": getattr(dialect_obj, "quotechar", '"'),
                },
                has_header,
            )
    except (csv.Error, OSError):
        return ({"delimiter": ",", "quotechar": '"'}, True)


def _fingerprint_path(abs_path: str) -> str:
    stat_info = os.stat(abs_path)
    raw = f"{abs_path}:{stat_info.st_size}:{stat_info.st_mtime}".encode()
    return hashlib.md5(raw).hexdigest()[:8]


def _error_command(
    runtime: ToolRuntime[HyperfocusContext, HyperfocusState], message: str
) -> Command:
    return Command(
        update={
            "messages": [
                ToolMessage(content=message, tool_call_id=runtime.tool_call_id)
            ]
        }
    )


CSV_TOOLS = [
    load_csv_file,
    describe_csv_table,
    query_csv_sql,
]
