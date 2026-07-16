"""
Import pdf_dtc_0708_0713.xlsx into ai_data.db as two separate tables:
  - dtc_info
  - dtc_trigger
"""

import sqlite3
import openpyxl
from pathlib import Path

XLSX_PATH = Path(__file__).resolve().parent.parent / "pdf_dtc_0708_0713.xlsx"
DB_PATH = Path(__file__).resolve().parent / "ai_data.db"


def sanitize_colname(name: str) -> str:
    """Normalise column names: uppercase, replace spaces with _."""
    return name.strip().upper().replace(" ", "_")


def import_sheet(db: sqlite3.Connection, sheet_name: str):
    wb = openpyxl.load_workbook(XLSX_PATH, read_only=True, data_only=True)
    ws = wb[sheet_name]

    rows_iter = ws.iter_rows(values_only=True)
    raw_headers = next(rows_iter)

    # 处理重复列名 → 加 _1, _2 后缀
    headers: list[str] = []
    seen: dict[str, int] = {}
    for h in raw_headers:
        name = sanitize_colname(h)
        if name in seen:
            seen[name] += 1
            name = f"{name}_{seen[name]}"
        else:
            seen[name] = 1
        headers.append(name)

    # 建表
    col_defs = ", ".join(f'"{h}" TEXT' for h in headers)
    table_name = sheet_name.replace(" ", "_")
    db.execute(f"DROP TABLE IF EXISTS [{table_name}]")
    db.execute(f"CREATE TABLE [{table_name}] ({col_defs})")
    print(f"  Created table [{table_name}] with {len(headers)} columns: {headers}")

    # 批量插入
    quoted_cols = ", ".join(f'"{h}"' for h in headers)
    placeholders = ", ".join(["?" for _ in headers])
    sql = f"INSERT INTO [{table_name}] ({quoted_cols}) VALUES ({placeholders})"

    batch: list[tuple] = []
    total = 0
    for row in rows_iter:
        # 将日期/数值序列化为字符串
        processed = tuple(str(v) if v is not None else None for v in row)
        batch.append(processed)
        total += 1
        if len(batch) >= 500:
            db.executemany(sql, batch)
            batch.clear()

    if batch:
        db.executemany(sql, batch)

    db.commit()
    print(f"  Inserted {total} rows into [{table_name}]")
    wb.close()


def main():
    print(f"XLSX: {XLSX_PATH}")
    print(f"DB:   {DB_PATH}")

    db = sqlite3.connect(str(DB_PATH))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=OFF")

    for sheet in ("dtc_info", "dtc_trigger"):
        print(f"\nImporting sheet [{sheet}] ...")
        import_sheet(db, sheet)

    # 验证
    cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [r[0] for r in cursor.fetchall()]
    print(f"\nAll tables in DB: {tables}")
    for t in ("dtc_info", "dtc_trigger"):
        cnt = db.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]
        print(f"  [{t}] row count: {cnt}")

    db.close()
    print("\nDone.")


if __name__ == "__main__":
    main()