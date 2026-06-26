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
# parser grammar: multiple joins, aggregate and scalar functions, a CASE
# expression, IN / IS NULL predicates, GROUP BY / HAVING and ORDER BY / LIMIT.
_PARSE_QUERY = """
SELECT
    o.order_id,
    o.order_date,
    c.customer_name,
    c.region,
    p.product_name,
    oi.quantity,
    oi.unit_price,
    oi.quantity * oi.unit_price AS line_total,
    UPPER(c.region) AS region_upper,
    CASE WHEN oi.quantity > 100 THEN 'bulk' ELSE 'standard' END AS order_type
FROM orders AS o
INNER JOIN customers AS c ON o.customer_id = c.customer_id
INNER JOIN order_items AS oi ON o.order_id = oi.order_id
INNER JOIN products AS p ON oi.product_id = p.product_id
WHERE o.order_date >= '2020-01-01'
    AND o.status IN ('shipped', 'delivered')
    AND c.region IS NOT NULL
GROUP BY
    o.order_id,
    o.order_date,
    c.customer_name,
    c.region,
    p.product_name,
    oi.quantity,
    oi.unit_price
HAVING SUM(oi.quantity) > 0
ORDER BY o.order_date DESC, o.order_id
LIMIT 100;
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


def test_parse_query(benchmark: pytest.FixtureRequest) -> None:
    """Benchmark parsing a moderately complex query."""
    benchmark(sqlfluff.parse, _PARSE_QUERY, dialect="ansi")


def test_lint_query(benchmark: pytest.FixtureRequest) -> None:
    """Benchmark linting a query with the full default rule set."""
    benchmark(sqlfluff.lint, _UNCLEAN_QUERY, dialect="ansi")


def test_fix_query(benchmark: pytest.FixtureRequest) -> None:
    """Benchmark fixing a query with style violations."""
    benchmark(sqlfluff.fix, _UNCLEAN_QUERY, dialect="ansi")
