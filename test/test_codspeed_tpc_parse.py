"""CodSpeed benchmark: parse the TPC-H/TPC-DS query suites via the Rust parser.

Four benchmarks are exposed to pytest-codspeed. `test_parse_tpch` and
`test_parse_tpcds` each parse the full query suite once per benchmark
iteration through `Linter.parse_string` with `use_rust_parser` enabled —
the full pipeline including Python-side BaseSegment tree building.

`test_native_ast_tpch` and `test_native_ast_tpcds` measure only the native
Rust pipeline on pre-lexed tokens: `RsParser.parse_match_result_from_tokens`
plus `RsMatchResult.apply_as_tree` (Node tree + arena construction), with no
Python-side tree building. They are the pytest counterparts of the
`native_ast_*` criterion benchmarks in `sqlfluffrs_benchmarks`.

Run instrumented (as CI does):
    pytest test/test_codspeed_tpc_parse.py --codspeed

Run as a plain correctness check (the `benchmark` fixture just calls the
wrapped function once when not run under `--codspeed`):
    pytest test/test_codspeed_tpc_parse.py
"""

import pathlib
import urllib.request
from urllib.error import URLError

import pytest

from sqlfluff.core import Linter
from sqlfluff.core.config import FluffConfig

# TPC-H/TPC-DS query fixtures, mirroring sqlfluffrs_benchmarks/build.rs so the
# query text matches the Rust criterion benches (tpc_bench.rs) exactly. Not
# committed to the repo; downloaded on first run and cached under `.cache`
# (gitignored).
_DORIS_SHA = "3a2d9d55f1e8e2d74187179ef89c36c8562815fd"
_DORIS_RAW_BASE = "https://raw.githubusercontent.com/apache/doris"
_TPCH_N = 22
_TPCDS_N = 99
_TPCDS_SPLIT = (14, 23, 24, 39)
_PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
_TPC_CACHE_DIR = _PROJECT_ROOT / "test" / ".cache" / "tpc"


def _normalize_tpc_sql(raw: str) -> str:
    # Mirrors sqlfluffrs_benchmarks/build.rs's `normalize`: Unix line endings,
    # trailing whitespace stripped per line, ending with a single newline.
    lines = raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return "\n".join(line.rstrip() for line in lines).rstrip("\n") + "\n"


def _download_tpc_sql(url: str) -> str:
    with urllib.request.urlopen(url, timeout=30) as resp:
        return resp.read().decode("utf-8")


def _ensure_tpc_fixtures() -> bool:
    """Download and cache the TPC-H/TPC-DS query fixtures if not already present.

    Mirrors sqlfluffrs_benchmarks/build.rs so the query text matches the Rust
    benchmarks exactly. Returns False if the fixtures are unavailable and
    couldn't be fetched (e.g. no network), in which case the caller should skip.
    """
    marker = _TPC_CACHE_DIR / ".doris-sha"
    if marker.exists() and marker.read_text().strip() == _DORIS_SHA:
        return True

    tpch_dir = _TPC_CACHE_DIR / "tpc-h"
    tpcds_dir = _TPC_CACHE_DIR / "tpc-ds"
    tpch_dir.mkdir(parents=True, exist_ok=True)
    tpcds_dir.mkdir(parents=True, exist_ok=True)

    try:
        for n in range(1, _TPCH_N + 1):
            url = f"{_DORIS_RAW_BASE}/{_DORIS_SHA}/tools/tpch-tools/queries/q{n}.sql"
            sql = _normalize_tpc_sql(_download_tpc_sql(url))
            (tpch_dir / f"{n}.sql").write_text(sql)

        for n in range(1, _TPCDS_N + 1):
            url = (
                f"{_DORIS_RAW_BASE}/{_DORIS_SHA}/tools/tpcds-tools/queries/"
                f"sf1/query{n}.sql"
            )
            sql = _normalize_tpc_sql(_download_tpc_sql(url))
            if n in _TPCDS_SPLIT:
                url2 = (
                    f"{_DORIS_RAW_BASE}/{_DORIS_SHA}/tools/tpcds-tools/queries/"
                    f"sf1/query{n}_1.sql"
                )
                part2 = _normalize_tpc_sql(_download_tpc_sql(url2))
                sql = f"{sql}\n{part2}"
            (tpcds_dir / f"{n}.sql").write_text(sql)
    except (OSError, URLError):
        return False

    marker.write_text(f"{_DORIS_SHA}\n")
    return True


def _load_tpc_queries(sub_dir: str, count: int) -> list[str]:
    d = _TPC_CACHE_DIR / sub_dir
    return [(d / f"{n}.sql").read_text() for n in range(1, count + 1)]


@pytest.fixture(scope="session")
def rust_linter() -> Linter:
    """Return a Linter configured to use the Rust parser."""
    cfg = FluffConfig(
        overrides={"dialect": "ansi", "use_rust_parser": True},
        ignore_local_config=True,
    )
    return Linter(config=cfg)


def _lex_token_sets(queries: list[str]) -> list[tuple[list, list, list]]:
    """Lex each query and split its tokens into (code, leading, trailing).

    Mirrors the trimming in `RustParser.parse`: the Rust parser is handed only
    the code portion of the token stream, while leading/trailing non-code
    tokens (e.g. an opening comment block, the trailing newline + end_of_file)
    are passed separately to `apply_as_tree` for gap-fill into the root node.
    """
    sqlfluffrs = pytest.importorskip("sqlfluffrs")
    lexer = sqlfluffrs.RsLexer(dialect="ansi")
    token_sets = []
    for sql in queries:
        tokens, _ = lexer._lex(sql)
        start = next((i for i, t in enumerate(tokens) if t.is_code), len(tokens))
        end = next(
            (i + 1 for i in range(len(tokens) - 1, -1, -1) if tokens[i].is_code),
            start,
        )
        token_sets.append((tokens[start:end], tokens[:start], tokens[end:]))
    return token_sets


@pytest.fixture(scope="session")
def rs_parser():
    """Return a bare RsParser (ANSI), skipping if sqlfluffrs is unavailable."""
    sqlfluffrs = pytest.importorskip("sqlfluffrs")
    return sqlfluffrs.RsParser(dialect="ansi")


@pytest.fixture(scope="session")
def tpch_token_sets(tpch_queries: list[str]) -> list[tuple[list, list, list]]:
    """Pre-lexed (code, leading, trailing) token sets for TPC-H."""
    return _lex_token_sets(tpch_queries)


@pytest.fixture(scope="session")
def tpcds_token_sets(tpcds_queries: list[str]) -> list[tuple[list, list, list]]:
    """Pre-lexed (code, leading, trailing) token sets for TPC-DS."""
    return _lex_token_sets(tpcds_queries)


@pytest.fixture(scope="session")
def tpch_queries() -> list[str]:
    """Return the cached TPC-H query fixtures, fetching them if needed."""
    if not _ensure_tpc_fixtures():
        pytest.skip("could not fetch TPC-H/TPC-DS fixtures and no cache present")
    return _load_tpc_queries("tpc-h", _TPCH_N)


@pytest.fixture(scope="session")
def tpcds_queries() -> list[str]:
    """Return the cached TPC-DS query fixtures, fetching them if needed."""
    if not _ensure_tpc_fixtures():
        pytest.skip("could not fetch TPC-H/TPC-DS fixtures and no cache present")
    return _load_tpc_queries("tpc-ds", _TPCDS_N)


def test_parse_tpch(benchmark, rust_linter: Linter, tpch_queries: list[str]) -> None:
    """Benchmark parsing the TPC-H query set with the Rust parser."""

    @benchmark
    def _run() -> None:
        for sql in tpch_queries:
            rust_linter.parse_string(sql)


def test_parse_tpcds(benchmark, rust_linter: Linter, tpcds_queries: list[str]) -> None:
    """Benchmark parsing the TPC-DS query set with the Rust parser."""

    @benchmark
    def _run() -> None:
        for sql in tpcds_queries:
            rust_linter.parse_string(sql)


def test_native_ast_tpch(benchmark, rs_parser, tpch_token_sets) -> None:
    """Benchmark the native Rust parse + AST build on the TPC-H query set."""

    @benchmark
    def _run() -> None:
        for code, leading, trailing in tpch_token_sets:
            rs_match = rs_parser.parse_match_result_from_tokens(code)
            rs_match.apply_as_tree(code, leading=leading, trailing=trailing)


def test_native_ast_tpcds(benchmark, rs_parser, tpcds_token_sets) -> None:
    """Benchmark the native Rust parse + AST build on the TPC-DS query set."""

    @benchmark
    def _run() -> None:
        for code, leading, trailing in tpcds_token_sets:
            rs_match = rs_parser.parse_match_result_from_tokens(code)
            rs_match.apply_as_tree(code, leading=leading, trailing=trailing)
