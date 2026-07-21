-- ALTER TABLE ... SET MERGEOUT with an arbitrary integer control value.
-- https://docs.vertica.com/latest/en/sql-reference/statements/alter-statements/alter-table/

ALTER TABLE public.store SET MERGEOUT 1;

ALTER TABLE public.store SET MERGEOUT 2;
