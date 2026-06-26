"""Performance benchmarks for the sqlfluff public API.

These benchmarks exercise the core hot paths of sqlfluff -- lexing/parsing,
linting and fixing -- through the simple public API (``sqlfluff.parse``,
``sqlfluff.lint`` and ``sqlfluff.fix``).

They are run by CodSpeed with the ``--codspeed`` flag and are intentionally kept
out of the main ``test`` suite so they do not affect the regular CI test run.
"""

import pytest

import sqlfluff

# A representative, moderately complex query that exercises a broad range of
# parser grammar: CTEs, joins, window functions, CASE expressions, subqueries
# and aggregate functions. Repeated to provide a realistic file-sized workload.
_BASE_QUERY = """
WITH regional_sales AS (
    SELECT
        r.region_name,
        o.order_date,
        SUM(oi.quantity * oi.unit_price) AS revenue
    FROM orders AS o
    INNER JOIN order_items AS oi ON o.order_id = oi.order_id
    LEFT JOIN regions AS r ON o.region_id = r.region_id
    WHERE o.order_date >= '2020-01-01'
        AND o.status IN ('shipped', 'delivered')
    GROUP BY r.region_name, o.order_date
),

ranked AS (
    SELECT
        region_name,
        order_date,
        revenue,
        ROW_NUMBER() OVER (
            PARTITION BY region_name
            ORDER BY revenue DESC
        ) AS revenue_rank,
        CASE
            WHEN revenue > 10000 THEN 'high'
            WHEN revenue > 1000 THEN 'medium'
            ELSE 'low'
        END AS revenue_band
    FROM regional_sales
)

SELECT
    region_name,
    order_date,
    revenue,
    revenue_rank,
    revenue_band
FROM ranked
WHERE revenue_rank <= 10
ORDER BY region_name, revenue_rank;
"""

# A version of the query with deliberate style issues (lower-case keywords and
# inconsistent indentation) so the linter and fixer have real work to do.
_UNCLEAN_QUERY = """
select
  a.id, a.name,
    b.value
from my_table a
join other_table b on a.id=b.id
where a.value > 10 and b.flag = TRUE
group by a.id,a.name,b.value
order by a.id
"""

_LARGE_QUERY = "\n".join(_BASE_QUERY for _ in range(5))


def test_parse_query(benchmark: pytest.FixtureRequest) -> None:
    """Benchmark parsing a moderately complex query."""
    benchmark(sqlfluff.parse, _BASE_QUERY, dialect="ansi")


def test_parse_large_query(benchmark: pytest.FixtureRequest) -> None:
    """Benchmark parsing a large (file-sized) SQL input."""
    benchmark(sqlfluff.parse, _LARGE_QUERY, dialect="ansi")


def test_lint_query(benchmark: pytest.FixtureRequest) -> None:
    """Benchmark linting a query with the full default rule set."""
    benchmark(sqlfluff.lint, _UNCLEAN_QUERY, dialect="ansi")


def test_fix_query(benchmark: pytest.FixtureRequest) -> None:
    """Benchmark fixing a query with style violations."""
    benchmark(sqlfluff.fix, _UNCLEAN_QUERY, dialect="ansi")
