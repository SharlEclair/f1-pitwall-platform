def test_toolchain_imports():
    import dbt.version  # noqa: F401
    import duckdb

    assert duckdb.connect(":memory:").execute("select 1").fetchone() == (1,)
