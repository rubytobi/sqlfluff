"""TPC-H and TPC-DS lex/parse benchmarks for pytest-codspeed.

Fixtures are fetched on first run from the Apache Doris repository at the
same pinned commit used by the Rust criterion benchmarks, then cached under
.cache/tpc-fixtures/ so subsequent runs are instant.

Run locally (wall-time measurement via pytest-benchmark):
    pytest test/benchmarks/test_tpc.py -v

Run under CodSpeed instrumentation (instruction count):
    pytest test/benchmarks/test_tpc.py --codspeed -v
"""

import urllib.request
from pathlib import Path
from typing import Generator

import pytest

from sqlfluff.core import FluffConfig
from sqlfluff.core.linter import Linter
from sqlfluff.core.parser import Lexer

# ── fixture provenance (mirrors sqlfluffrs_benchmarks/build.rs) ───────────────
_DORIS_SHA = "3a2d9d55f1e8e2d74187179ef89c36c8562815fd"
_RAW_BASE = f"https://raw.githubusercontent.com/apache/doris/{_DORIS_SHA}"
_TPCH_N = 22
_TPCDS_N = 99
# Queries that the TPC-DS spec splits into two statements; Doris stores them
# as query{n}.sql + query{n}_1.sql, which we concatenate like build.rs does.
_TPCDS_SPLIT = {14, 23, 24, 39}

# .cache/ is already gitignored; fixtures survive across local runs.
_CACHE_DIR = Path(__file__).parents[2] / ".cache" / "tpc-fixtures"


# ── download helpers ──────────────────────────────────────────────────────────

def _fetch(url: str) -> str:
    with urllib.request.urlopen(url, timeout=30) as resp:
        return resp.read().decode()


def _normalize(raw: str) -> str:
    """Unix line endings, no trailing whitespace per line, single trailing newline."""
    lines = raw.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    return "\n".join(line.rstrip() for line in lines) + "\n"


def _load_tpch() -> list[str]:
    tpch_dir = _CACHE_DIR / "tpc-h"
    tpch_dir.mkdir(parents=True, exist_ok=True)
    sqls = []
    for n in range(1, _TPCH_N + 1):
        path = tpch_dir / f"{n}.sql"
        if not path.exists():
            url = f"{_RAW_BASE}/tools/tpch-tools/queries/q{n}.sql"
            path.write_text(_normalize(_fetch(url)))
        sqls.append(path.read_text())
    return sqls


def _load_tpcds() -> list[str]:
    tpcds_dir = _CACHE_DIR / "tpc-ds"
    tpcds_dir.mkdir(parents=True, exist_ok=True)
    sqls = []
    for n in range(1, _TPCDS_N + 1):
        path = tpcds_dir / f"{n}.sql"
        if not path.exists():
            url = f"{_RAW_BASE}/tools/tpcds-tools/queries/sf1/query{n}.sql"
            sql = _normalize(_fetch(url))
            if n in _TPCDS_SPLIT:
                url2 = f"{_RAW_BASE}/tools/tpcds-tools/queries/sf1/query{n}_1.sql"
                sql += "\n" + _normalize(_fetch(url2))
            path.write_text(sql)
        sqls.append(path.read_text())
    return sqls


# ── session-scoped fixtures (downloaded once, reused across all benchmarks) ───

@pytest.fixture(scope="session")
def tpch_sqls() -> list[str]:
    """All 22 TPC-H query strings, fetched once per session."""
    return _load_tpch()


@pytest.fixture(scope="session")
def tpcds_sqls() -> list[str]:
    """All 99 TPC-DS query strings, fetched once per session."""
    return _load_tpcds()


@pytest.fixture(scope="session")
def ansi_lexer() -> Generator[Lexer, None, None]:
    config = FluffConfig(overrides={"dialect": "ansi"})
    yield Lexer(config=config)


@pytest.fixture(scope="session")
def ansi_linter() -> Generator[Linter, None, None]:
    config = FluffConfig(overrides={"dialect": "ansi"})
    yield Linter(config=config)


# ── TPC-H benchmarks ──────────────────────────────────────────────────────────

def test_lex_tpch(benchmark, ansi_lexer, tpch_sqls):
    """Lex all 22 TPC-H queries (Q1–Q22) in one pass."""
    benchmark(lambda: [ansi_lexer.lex(sql) for sql in tpch_sqls])


def test_parse_tpch(benchmark, ansi_linter, tpch_sqls):
    """Lex and parse all 22 TPC-H queries (Q1–Q22) in one pass."""
    benchmark(lambda: [ansi_linter.parse_string(sql) for sql in tpch_sqls])


# ── TPC-DS benchmarks ─────────────────────────────────────────────────────────

def test_lex_tpcds(benchmark, ansi_lexer, tpcds_sqls):
    """Lex all 99 TPC-DS queries (Q1–Q99) in one pass."""
    benchmark(lambda: [ansi_lexer.lex(sql) for sql in tpcds_sqls])


def test_parse_tpcds(benchmark, ansi_linter, tpcds_sqls):
    """Lex and parse all 99 TPC-DS queries (Q1–Q99) in one pass."""
    benchmark(lambda: [ansi_linter.parse_string(sql) for sql in tpcds_sqls])
