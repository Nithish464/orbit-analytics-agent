import os, sqlite3
from pathlib import Path

DB_PATH = Path(os.getenv("ORBIT_DB_PATH", str(Path(__file__).resolve().parent.parent / "orbit.db")))
SCHEMA = {
    "customers": ["customer_id","customer_name","region","segment","joined_date"],
    "products": ["product_id","product_name","category","unit_price"],
    "orders": ["order_id","customer_id","order_date","status"],
    "order_items": ["item_id","order_id","product_id","quantity","unit_price"],
}

def get_connection(readonly=False):
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if readonly and DB_PATH.exists():
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    else:
        conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def initialize_database():
    conn = get_connection()
    cur = conn.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS customers(customer_id INTEGER PRIMARY KEY, customer_name TEXT NOT NULL, region TEXT NOT NULL, segment TEXT NOT NULL, joined_date TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS products(product_id INTEGER PRIMARY KEY, product_name TEXT NOT NULL, category TEXT NOT NULL, unit_price REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS orders(order_id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL, order_date TEXT NOT NULL, status TEXT NOT NULL, FOREIGN KEY(customer_id) REFERENCES customers(customer_id));
    CREATE TABLE IF NOT EXISTS order_items(item_id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL, product_id INTEGER NOT NULL, quantity INTEGER NOT NULL, unit_price REAL NOT NULL, FOREIGN KEY(order_id) REFERENCES orders(order_id), FOREIGN KEY(product_id) REFERENCES products(product_id));
    """)
    if cur.execute("SELECT COUNT(*) FROM customers").fetchone()[0] == 0:
        customers = [
            (1,"Aarav Mehta","North","Consumer","2023-01-12"),(2,"Diya Iyer","South","Corporate","2023-02-18"),
            (3,"Kabir Shah","West","Consumer","2023-03-05"),(4,"Ananya Rao","South","Small Business","2023-04-21"),
            (5,"Ishaan Nair","East","Corporate","2023-05-11"),(6,"Meera Das","East","Consumer","2023-06-19"),
            (7,"Arjun Kumar","South","Small Business","2023-07-02"),(8,"Sara Khan","North","Corporate","2023-08-14"),
            (9,"Vihaan Patel","West","Consumer","2023-09-09"),(10,"Tara Menon","South","Consumer","2023-10-27")]
        products = [(1,"Pulse Headphones","Electronics",89),(2,"Arc Smartwatch","Electronics",149),(3,"Everyday Backpack","Accessories",59),(4,"Studio Desk","Furniture",329),(5,"Cloud Lamp","Home",45),(6,"Sprint Sneakers","Fashion",110),(7,"Brew Coffee Kit","Home",72)]
        orders = [
            (1001,1,"2024-01-08","delivered"),(1002,2,"2024-01-19","delivered"),(1003,3,"2024-02-03","returned"),(1004,4,"2024-02-22","delivered"),
            (1005,5,"2024-03-11","shipped"),(1006,6,"2024-03-27","delivered"),(1007,7,"2024-04-06","delivered"),(1008,8,"2024-04-18","cancelled"),
            (1009,9,"2024-05-09","delivered"),(1010,10,"2024-05-25","delivered"),(1011,1,"2024-06-04","delivered"),(1012,2,"2024-06-16","shipped"),
            (1013,3,"2024-07-02","delivered"),(1014,4,"2024-07-20","delivered"),(1015,5,"2024-08-12","returned"),(1016,6,"2024-08-29","delivered"),
            (1017,7,"2024-09-07","delivered"),(1018,8,"2024-09-23","delivered"),(1019,9,"2024-10-10","shipped"),(1020,10,"2024-10-28","delivered"),
            (1021,1,"2024-11-05","delivered"),(1022,2,"2024-11-19","delivered"),(1023,3,"2024-12-02","delivered"),(1024,4,"2024-12-17","delivered"),
            (1025,5,"2025-01-09","delivered"),(1026,6,"2025-01-24","shipped"),(1027,7,"2025-02-08","delivered"),(1028,8,"2025-02-21","delivered"),
            (1029,9,"2025-03-06","delivered"),(1030,10,"2025-03-18","delivered")]
        price = {p[0]:p[3] for p in products}
        items=[]
        for i,o in enumerate(orders):
            a=(i%7)+1; b=((i*3+2)%7)+1
            items.append((i*2+1,o[0],a,(i%4)+1,price[a]))
            if b != a: items.append((i*2+2,o[0],b,((i+1)%3)+1,price[b]))
        cur.executemany("INSERT INTO customers VALUES (?,?,?,?,?)",customers)
        cur.executemany("INSERT INTO products VALUES (?,?,?,?)",products)
        cur.executemany("INSERT INTO orders VALUES (?,?,?,?)",orders)
        cur.executemany("INSERT INTO order_items VALUES (?,?,?,?,?)",items)
    conn.commit()
    conn.close()

def get_schema():
    return [{"table": t, "columns": c} for t,c in SCHEMA.items()]
