"""OutputSink — in-memory row accumulator that flushes to parquet files.

Each row carries mandatory context columns (mc_run, t, nation_id) plus
arbitrary keyword fields.  Rows are grouped by table_name; flush() writes
one parquet file per table.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Any


class OutputSink:
    """Accumulate records in memory; flush to parquet on demand.

    Parameters
    ----------
    output_dir : str | Path | None
        Default destination directory.  Can be overridden per flush() call.
    """

    def __init__(self, output_dir: "str | Path | None" = None) -> None:
        self.output_dir: Path | None = Path(output_dir) if output_dir else None
        self._rows: dict[str, list[dict]] = defaultdict(list)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record(
        self,
        table_name: str,
        mc_run: int,
        t: int,
        nation_id: str,
        **fields: Any,
    ) -> None:
        """Append one row to the named table."""
        row = {"mc_run": mc_run, "t": t, "nation_id": nation_id, **fields}
        self._rows[table_name].append(row)

    def flush(self, output_dir: "str | Path | None" = None) -> dict[str, Path]:
        """Write all accumulated rows to parquet; one file per table_name.

        Clears the in-memory buffer after writing.  Returns a mapping of
        table_name → Path of the written file.
        """
        import pandas as pd
        import pyarrow as pa
        import pyarrow.parquet as pq

        dest = Path(output_dir) if output_dir else self.output_dir
        if dest is None:
            raise ValueError(
                "output_dir must be provided either at construction or to flush()"
            )
        dest.mkdir(parents=True, exist_ok=True)

        written: dict[str, Path] = {}
        for table_name, rows in self._rows.items():
            if not rows:
                continue
            path = dest / f"{table_name}.parquet"
            table = pa.Table.from_pandas(pd.DataFrame(rows))
            pq.write_table(table, path)
            written[table_name] = path

        self._rows.clear()
        return written

    def n_pending_rows(self, table_name: str | None = None) -> int:
        """Number of rows accumulated but not yet flushed."""
        if table_name is not None:
            return len(self._rows.get(table_name, []))
        return sum(len(rows) for rows in self._rows.values())
