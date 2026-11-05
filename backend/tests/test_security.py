
import pytest

from app.security import (
    validate_question_intent,
    validate_readonly_sql,
)


def test_select_allowed():
    ok, sql = validate_readonly_sql("SELECT status FROM orders")
    assert ok
    assert "LIMIT 100" in sql


def test_write_rejected():
    ok, message = validate_readonly_sql("INSERT INTO orders VALUES (1)")
    assert not ok
    assert "Only SELECT" in message


def test_multiple_statements_rejected():
    ok, _ = validate_readonly_sql(
        "SELECT * FROM orders; DROP TABLE orders"
    )
    assert not ok


def test_unknown_table_rejected():
    ok, _ = validate_readonly_sql("SELECT * FROM secrets")
    assert not ok


def test_comments_rejected():
    ok, _ = validate_readonly_sql("SELECT * FROM orders -- hi")
    assert not ok


def test_unknown_column_rejected():
    ok, message = validate_readonly_sql(
        "SELECT password_hash FROM customers"
    )
    assert not ok
    assert "Unapproved column" in message


def test_external_database_reference_rejected():
    ok, message = validate_readonly_sql("SELECT * FROM main.orders")
    assert not ok
    assert "External database" in message


def test_limit_over_maximum_rejected():
    ok, message = validate_readonly_sql(
        "SELECT * FROM orders LIMIT 101"
    )
    assert not ok
    assert "cannot exceed" in message


def test_zero_limit_rejected():
    ok, message = validate_readonly_sql(
        "SELECT * FROM orders LIMIT 0"
    )
    assert not ok
    assert "at least 1" in message


def test_question_length_limit():
    with pytest.raises(ValueError, match="500 characters"):
        validate_question_intent("revenue " + "x" * 510)


def test_ambiguous_unqualified_column_rejected():
    sql = """
        SELECT customer_id
        FROM customers
        JOIN orders
        ON customers.customer_id = orders.customer_id
    """
    ok, message = validate_readonly_sql(sql)
    assert not ok
    assert "Ambiguous column" in message


def test_qualified_column_allowed():
    sql = """
        SELECT customers.customer_id
        FROM customers
        JOIN orders
        ON customers.customer_id = orders.customer_id
    """
    ok, result = validate_readonly_sql(sql)
    assert ok, result
    assert "customer_id" in result.lower()


def test_self_join_ambiguous_column_rejected():
    sql = """
        SELECT customer_id
        FROM customers c1
        JOIN customers c2
        ON c1.customer_id = c2.customer_id
    """
    ok, message = validate_readonly_sql(sql)
    assert not ok
    assert "Ambiguous column" in message


# SQL scope regression tests


def test_cte_query_allowed():
    sql = """
        WITH customer_orders AS (
            SELECT customer_id
            FROM orders
        )
        SELECT customer_id
        FROM customer_orders
    """
    ok, result = validate_readonly_sql(sql)
    assert ok, result


def test_nested_subquery_allowed():
    sql = """
        SELECT customer_id
        FROM customers
        WHERE customer_id IN (
            SELECT customer_id
            FROM orders
        )
    """
    ok, result = validate_readonly_sql(sql)
    assert ok, result


def test_correlated_subquery_allowed():
    sql = """
        SELECT c.customer_id
        FROM customers AS c
        WHERE EXISTS (
            SELECT 1
            FROM orders AS o
            WHERE o.customer_id = c.customer_id
        )
    """
    ok, result = validate_readonly_sql(sql)
    assert ok, result
def test_write_operation_inside_cte_rejected():
    sql = """
        WITH modified AS (
            DELETE FROM orders
            RETURNING customer_id
        )
        SELECT customer_id FROM modified
    """
    ok, message = validate_readonly_sql(sql)
    assert not ok


def test_unknown_table_inside_nested_query_rejected():
    sql = """
        SELECT customer_id
        FROM customers
        WHERE customer_id IN (
            SELECT customer_id
            FROM secret_table
        )
    """
    ok, message = validate_readonly_sql(sql)
    assert not ok


def test_forbidden_function_inside_subquery_rejected():
    sql = """
        SELECT customer_id
        FROM customers
        WHERE customer_id IN (
            SELECT readfile('/etc/passwd')
        )
    """
    ok, message = validate_readonly_sql(sql)
    assert not ok