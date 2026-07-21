-- CREATE TABLE with Doris fixed-range partitions (VALUES [lower, upper)).
-- https://doris.apache.org/docs/table-design/data-partitioning/manual-partitioning

CREATE TABLE t_fixed_range
(
    c1 INT,
    c2 DATE NOT NULL
)
DUPLICATE KEY(c1)
PARTITION BY RANGE(c2)
(
    PARTITION p1 VALUES (('2020-01-01'), ('2020-02-01')),
    PARTITION p2 VALUES (('2020-02-01'), ('2020-03-01'))
)
DISTRIBUTED BY HASH(c1) BUCKETS 1
PROPERTIES (
    'replication_num' = '1'
);
