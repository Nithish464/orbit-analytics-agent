from app.security import validate_readonly_sql

def test_select_allowed():
    ok,sql=validate_readonly_sql("SELECT status FROM orders")
    assert ok and "LIMIT 100" in sql
def test_write_rejected():
    ok,msg=validate_readonly_sql("INSERT INTO orders VALUES (1)")
    assert not ok and "Only SELECT" in msg
def test_multiple_statements_rejected():
    assert not validate_readonly_sql("SELECT * FROM orders; DROP TABLE orders")[0]
def test_unknown_table_rejected():
    assert not validate_readonly_sql("SELECT * FROM secrets")[0]
def test_comments_rejected():
    assert not validate_readonly_sql("SELECT * FROM orders -- hi")[0]


def test_unknown_column_rejected():
    ok, message = validate_readonly_sql(
        "SELECT password_hash FROM customers"
    )
    assert not ok
    assert "Unapproved column" in message


def test_external_database_reference_rejected():
    ok, message = validate_readonly_sql(
        "SELECT * FROM main.orders"
    )
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
    from app.security import validate_question_intent

    try:
        validate_question_intent("revenue " + "x" * 510)
    except ValueError as error:
        assert "500 characters" in str(error)
    else:
        raise AssertionError("Oversized question should be rejected")
