import os, tempfile
from pathlib import Path
_tmp=tempfile.TemporaryDirectory()
os.environ["ORBIT_DB_PATH"]=str(Path(_tmp.name)/"test.db")
from app.database import initialize_database
from app.agents import execute_workflow

def setup_module(): initialize_database()
def test_total_revenue():
    r=execute_workflow("What is our total revenue?")
    assert r["row_count"]==1 and r["rows"][0]["total_revenue"]>0 and len(r["steps"])==5
def test_monthly_chart():
    r=execute_workflow("Show monthly revenue for 2024")
    assert r["row_count"]>=10 and r["chart"]["type"]=="bar"
def test_top_products():
    r=execute_workflow("Which are the top 5 products by revenue?")
    assert r["row_count"]==5 and "product_name" in r["columns"]
