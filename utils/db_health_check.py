import argparse
import json
import os
import sqlite3
import time


def _connect(db_path):
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def _scalar(conn, sql, params=()):
    row = conn.execute(sql, params).fetchone()
    return row[0] if row else None


def _print_header(title):
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def _collection_counts(conn):
    rows = conn.execute(
        "SELECT collection, COUNT(*) AS cnt FROM __documents GROUP BY collection ORDER BY cnt DESC, collection"
    ).fetchall()
    return [(r["collection"], r["cnt"]) for r in rows]


def _list_indexes(conn):
    rows = conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='__documents' ORDER BY name"
    ).fetchall()
    return [(r["name"], r["sql"] or "") for r in rows]


def _sample_value(conn, collection, key):
    row = conn.execute(
        "SELECT json_extract(data, ?) AS v FROM __documents WHERE collection = ? AND json_extract(data, ?) IS NOT NULL LIMIT 1",
        (f"$.{key}", collection, f"$.{key}"),
    ).fetchone()
    return row["v"] if row else None


def _benchmark_query(conn, label, sql, params=(), loops=200):
    plan_rows = conn.execute("EXPLAIN QUERY PLAN " + sql, params).fetchall()
    plan = " | ".join(str(dict(r)) for r in plan_rows)

    # Warm-up
    conn.execute(sql, params).fetchall()

    start = time.perf_counter()
    total_rows = 0
    for _ in range(loops):
        total_rows += len(conn.execute(sql, params).fetchall())
    elapsed_ms = (time.perf_counter() - start) * 1000.0

    avg_ms = elapsed_ms / loops if loops else elapsed_ms
    print(f"- {label}")
    print(f"  avg_ms={avg_ms:.4f} loops={loops} total_rows={total_rows}")
    print(f"  plan={plan}")


def run(db_path, loops=200):
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database not found: {db_path}")

    with _connect(db_path) as conn:
        _print_header("Database Info")
        print(f"path: {os.path.abspath(db_path)}")
        print(f"size_bytes: {os.path.getsize(db_path)}")
        print(f"sqlite_version: {sqlite3.sqlite_version}")
        print(f"journal_mode: {_scalar(conn, 'PRAGMA journal_mode')}")
        print(f"synchronous: {_scalar(conn, 'PRAGMA synchronous')}")
        print(f"foreign_keys: {_scalar(conn, 'PRAGMA foreign_keys')}")

        _print_header("Collection Counts")
        for name, cnt in _collection_counts(conn):
            print(f"- {name}: {cnt}")

        _print_header("__documents Indexes")
        for name, sql in _list_indexes(conn):
            print(f"- {name}")
            if sql:
                print(f"  {sql}")

        _print_header("Benchmarks")
        university_id = _sample_value(conn, "colleges", "university")
        degree_id = _sample_value(conn, "majors", "degree")
        department_id = _sample_value(conn, "majors", "department")
        user_id = _sample_value(conn, "reports", "user")
        industry_type = _sample_value(conn, "work_keywords", "industryType")
        job_profile = _sample_value(conn, "work_keywords", "jobProfile")

        _benchmark_query(
            conn,
            "colleges by university",
            "SELECT id FROM __documents WHERE collection='colleges' AND json_extract(data, '$.university') = ?",
            (str(university_id or ""),),
            loops,
        )
        _benchmark_query(
            conn,
            "colleges by status+active",
            "SELECT id FROM __documents WHERE collection='colleges' AND json_extract(data, '$.approvalStatus') = 'approved' AND json_extract(data, '$.isActive') = 1",
            (),
            loops,
        )
        _benchmark_query(
            conn,
            "majors by degree",
            "SELECT id FROM __documents WHERE collection='majors' AND json_extract(data, '$.degree') = ?",
            (str(degree_id or ""),),
            loops,
        )
        _benchmark_query(
            conn,
            "majors by degree+department",
            "SELECT id FROM __documents WHERE collection='majors' AND json_extract(data, '$.degree') = ? AND json_extract(data, '$.department') = ?",
            (str(degree_id or ""), str(department_id or "")),
            loops,
        )
        _benchmark_query(
            conn,
            "users by role+active",
            "SELECT id FROM __documents WHERE collection='users' AND json_extract(data, '$.role') = 'student' AND json_extract(data, '$.isActive') = 1",
            (),
            loops,
        )
        _benchmark_query(
            conn,
            "reports by user",
            "SELECT id FROM __documents WHERE collection='reports' AND json_extract(data, '$.user') = ?",
            (str(user_id or ""),),
            loops,
        )
        _benchmark_query(
            conn,
            "work keywords by industry/job",
            "SELECT id FROM __documents WHERE collection='work_keywords' AND lower(json_extract(data, '$.industryType')) = lower(?) AND lower(json_extract(data, '$.jobProfile')) = lower(?) AND json_extract(data, '$.isActive') = 1",
            (str(industry_type or ""), str(job_profile or "")),
            loops,
        )


def main():
    parser = argparse.ArgumentParser(description="DB health and benchmark report for __documents SQLite store")
    parser.add_argument("--db", default=os.path.join("data", "app.db"), help="Path to SQLite .db file")
    parser.add_argument("--loops", type=int, default=200, help="Benchmark loops per query")
    args = parser.parse_args()
    run(args.db, loops=max(1, int(args.loops or 1)))


if __name__ == "__main__":
    main()
