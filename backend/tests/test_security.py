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
