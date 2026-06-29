from dbt.adapters.graphbridge.connections import _is_sql, _normalise_statement


def test_normalise_statement_removes_dbt_depends_on_comments():
    sql = """
    -- depends_on: {{ ref('company_node') }}
    SELECT *
    FROM stg_companies
    """

    assert _normalise_statement(sql) == "SELECT * FROM STG_COMPANIES"


def test_is_sql_detects_select_after_comments():
    sql = """
    -- dbt generated dependency comment
    WITH companies AS (
        SELECT * FROM stg_companies
    )
    SELECT * FROM companies
    """

    assert _is_sql(sql)


def test_is_sql_does_not_classify_cypher():
    assert not _is_sql("MATCH (n) RETURN n")
