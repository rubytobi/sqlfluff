-- CREATE TABLE with the Impala CACHED IN / UNCACHED clause.
-- https://impala.apache.org/docs/build/html/topics/impala_create_table.html

CREATE TABLE cached_tbl (
    id INT,
    name STRING
)
STORED AS PARQUET
CACHED IN 'pool_name' WITH REPLICATION = 3;

CREATE TABLE cached_no_replication (
    id INT
)
STORED AS PARQUET
CACHED IN 'pool_name';

CREATE TABLE uncached_tbl (
    id INT
)
STORED AS PARQUET
UNCACHED;

CREATE TABLE cached_ctas
STORED AS PARQUET
CACHED IN 'pool_name' WITH REPLICATION = 2
AS SELECT id FROM other_tbl;
