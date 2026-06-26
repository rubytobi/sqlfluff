"""TPC-H and TPC-DS lex/parse benchmarks for pytest-codspeed.

Run locally (wall-time measurement via pytest-benchmark):
    pytest test/benchmarks/test_tpc.py -v

Run under CodSpeed instrumentation (instruction count):
    pytest test/benchmarks/test_tpc.py --codspeed -v

Scope note
──────────
Lex benchmarks run the full query set (22 TPC-H / 99 TPC-DS) because
lexing is shallow and completes quickly under Valgrind.

Parse benchmarks use a single representative query per suite.  Parsing
triggers deep recursive grammar matching which generates far more
callgrind data per second than lexing; running all queries exhausts the
CodSpeed runner's memory and causes a segfault (exit 139).  A single-
query benchmark captures the same regression signal: a 5% regression in
parse time shows as 5% more instructions whether you measure 1 query or
all of them.
"""

from sqlfluff.core.linter import Linter
from sqlfluff.core.parser import Lexer

# Number of queries used for parse benchmarks.  Keep low enough that the
# benchmark body completes in ~30 s under Valgrind callgrind.
_PARSE_N = 1


def test_lex_tpch(benchmark, ansi_lexer: Lexer, tpch_sqls: list[str]):
    """Lex all 22 TPC-H queries (Q1–Q22) in one pass."""
    benchmark(lambda: [ansi_lexer.lex(sql) for sql in tpch_sqls])


def test_parse_tpch(benchmark, ansi_linter: Linter, tpch_sqls: list[str]):
    """Parse TPC-H Q1 as a representative single-query benchmark."""
    sqls = tpch_sqls[:_PARSE_N]
    benchmark(lambda: [ansi_linter.parse_string(sql) for sql in sqls])


def test_lex_tpcds(benchmark, ansi_lexer: Lexer, tpcds_sqls: list[str]):
    """Lex all 99 TPC-DS queries (Q1–Q99) in one pass."""
    benchmark(lambda: [ansi_lexer.lex(sql) for sql in tpcds_sqls])


def test_parse_tpcds(benchmark, ansi_linter: Linter, tpcds_sqls: list[str]):
    """Parse TPC-DS Q1 as a representative single-query benchmark."""
    sqls = tpcds_sqls[:_PARSE_N]
    benchmark(lambda: [ansi_linter.parse_string(sql) for sql in sqls])
