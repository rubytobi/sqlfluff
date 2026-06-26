"""Shared fixtures for the benchmark suite.

TPC-H and TPC-DS SQL files are fetched on first run from the Apache Doris
repository at the same pinned commit used by the Rust criterion benchmarks
(sqlfluffrs_benchmarks/build.rs) and cached under .cache/tpc-fixtures/.
The .cache/ directory is already gitignored, so fixtures survive local runs
without being committed.

If the pinned SHA or the split-query list ever changes, update both this
file and build.rs to keep them in sync.
"""

import urllib.request
from pathlib import Path
from typing import Generator

import pytest

from sqlfluff.core import FluffConfig
from sqlfluff.core.linter import Linter
from sqlfluff.core.parser import Lexer

# ── provenance (keep in sync with sqlfluffrs_benchmarks/build.rs) ────────────
_DORIS_SHA = "3a2d9d55f1e8e2d74187179ef89c36c8562815fd"
_RAW_BASE = f"https://raw.githubusercontent.com/apache/doris/{_DORIS_SHA}"
_TPCH_N = 22
_TPCDS_N = 99
# Queries the TPC-DS spec defines as two independent statements; Doris stores
# them as query{n}.sql + query{n}_1.sql — concatenated here as build.rs does.
_TPCDS_SPLIT = {14, 23, 24, 39}

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
            path.write_text(_normalize(_fetch(
                f"{_RAW_BASE}/tools/tpch-tools/queries/q{n}.sql"
            )))
        sqls.append(path.read_text())
    return sqls


def _load_tpcds() -> list[str]:
    tpcds_dir = _CACHE_DIR / "tpc-ds"
    tpcds_dir.mkdir(parents=True, exist_ok=True)
    sqls = []
    for n in range(1, _TPCDS_N + 1):
        path = tpcds_dir / f"{n}.sql"
        if not path.exists():
            sql = _normalize(_fetch(
                f"{_RAW_BASE}/tools/tpcds-tools/queries/sf1/query{n}.sql"
            ))
            if n in _TPCDS_SPLIT:
                sql += "\n" + _normalize(_fetch(
                    f"{_RAW_BASE}/tools/tpcds-tools/queries/sf1/query{n}_1.sql"
                ))
            path.write_text(sql)
        sqls.append(path.read_text())
    return sqls


# ── session-scoped fixtures ───────────────────────────────────────────────────

@pytest.fixture(scope="session")
def tpch_sqls() -> list[str]:
    """All 22 TPC-H query strings, downloaded once and cached."""
    return _load_tpch()


@pytest.fixture(scope="session")
def tpcds_sqls() -> list[str]:
    """All 99 TPC-DS query strings, downloaded once and cached."""
    return _load_tpcds()


@pytest.fixture(scope="session")
def ansi_lexer() -> Generator[Lexer, None, None]:
    yield Lexer(config=FluffConfig(overrides={"dialect": "ansi"}))


@pytest.fixture(scope="session")
def ansi_linter() -> Generator[Linter, None, None]:
    yield Linter(config=FluffConfig(overrides={"dialect": "ansi"}))
