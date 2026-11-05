
import os
import sqlite3
import time
from pathlib import Path
from typing import Optional


DB_PATH = Path(
    os.getenv(
        "ORBIT_DB_PATH",
        str(Path(__file__).resolve().parent.parent / "orbit.db"),
    )
)


SCHEMA = {
    "customers": [
        "customer_id",
        "customer_name",
        "region",
        "segment",
        "joined_date",
    ],
    "products": [
        "product_id",
        "product_name",
        "category",
        "unit_price",
    ],
    "orders": [
        "order_id",
        "customer_id",
        "order_date",
        "status",
    ],
    "order_items": [
        "item_id",
        "order_id",
        "product_id",
        "quantity",
        "unit_price",
    ],
}


# SQLite operations permitted during read-only queries.
READ_ONLY_ACTIONS = {
    sqlite3.SQLITE_SELECT,
    sqlite3.SQLITE_READ,
    sqlite3.SQLITE_FUNCTION,
    sqlite3.SQLITE_RECURSIVE,
}


BLOCKED_FUNCTIONS = {
    "load_extension",
    "readfile",
    "writefile",
}


# SQL execution timeout configuration.
QUERY_TIMEOUT_SECONDS = 5.0
SQLITE_PROGRESS_OPCODES = 1000


def _readonly_authorizer(
    action: int,
    arg1: Optional[str],
    arg2: Optional[str],
    database_name: Optional[str],
    trigger_name: Optional[str],
) -> int:
    """
    SQLite-level authorization for read-only connections.

    Only SELECT, READ and approved function operations
    are permitted.
    """

    if action not in READ_ONLY_ACTIONS:
        return sqlite3.SQLITE_DENY

    if action == sqlite3.SQLITE_READ:
        table_name = (arg1 or "").lower()

        if table_name not in SCHEMA:
            return sqlite3.SQLITE_DENY

    if action == sqlite3.SQLITE_FUNCTION:
        function_name = (arg2 or arg1 or "").lower()

        if function_name in BLOCKED_FUNCTIONS:
            return sqlite3.SQLITE_DENY

    return sqlite3.SQLITE_OK


def _configure_query_timeout(
    connection: sqlite3.Connection,
) -> None:
    """
    Configure a per-statement execution timeout.

    A fresh deadline is created whenever SQLite starts
    executing a new statement.

    The progress handler interrupts a query when its
    execution exceeds QUERY_TIMEOUT_SECONDS.
    """

    query_deadline = [0.0]

    def reset_query_deadline(sql: str) -> None:
        query_deadline[0] = (
            time.monotonic() + QUERY_TIMEOUT_SECONDS
        )

    def check_query_timeout() -> int:
        if time.monotonic() >= query_deadline[0]:
            return 1

        return 0

    connection.set_trace_callback(reset_query_deadline)

    connection.set_progress_handler(
        check_query_timeout,
        SQLITE_PROGRESS_OPCODES,
    )


def get_connection(
    readonly: bool = False,
) -> sqlite3.Connection:
    """
    Create a SQLite connection.

    Writable connections are used only for initialization
    and database maintenance.

    Read-only connections require an existing database file,
    enable query_only mode, install a SQLite authorizer,
    and enforce a query execution timeout.
    """

    resolved_path = DB_PATH.resolve()

    if readonly:
        if not resolved_path.is_file():
            raise FileNotFoundError(
                f"Database does not exist: {resolved_path}"
            )

        database_uri = (
            f"file:{resolved_path.as_posix()}?mode=ro"
        )

        connection = sqlite3.connect(
            database_uri,
            uri=True,
            timeout=10,
        )

    else:
        resolved_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        connection = sqlite3.connect(
            resolved_path,
            timeout=10,
        )

    try:
        connection.row_factory = sqlite3.Row

        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")

        if readonly:
            connection.execute("PRAGMA query_only = ON")
            connection.set_authorizer(_readonly_authorizer)

            _configure_query_timeout(connection)

        return connection

    except Exception:
        connection.close()
        raise


def _create_performance_indexes(
    cursor: sqlite3.Cursor,
) -> None:
    """
    Create indexes for frequently used ORBIT query patterns.

    These indexes support JOIN operations and the year
    expression used by the deterministic SQL builder.
    """

    cursor.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_orders_customer_id
        ON orders(customer_id);

        CREATE INDEX IF NOT EXISTS idx_order_items_order_id
        ON order_items(order_id);

        CREATE INDEX IF NOT EXISTS idx_order_items_product_id
        ON order_items(product_id);

        CREATE INDEX IF NOT EXISTS idx_orders_year
        ON orders(substr(order_date, 1, 4));
        """
    )


def initialize_database() -> None:
    """
    Initialize the ORBIT analytics database, create performance
    indexes and insert demo data when the customers table is empty.
    """

    conn = get_connection(readonly=False)

    try:
        cur = conn.cursor()

        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS customers (
                customer_id INTEGER PRIMARY KEY,
                customer_name TEXT NOT NULL,
                region TEXT NOT NULL,
                segment TEXT NOT NULL,
                joined_date TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS products (
                product_id INTEGER PRIMARY KEY,
                product_name TEXT NOT NULL,
                category TEXT NOT NULL,
                unit_price REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS orders (
                order_id INTEGER PRIMARY KEY,
                customer_id INTEGER NOT NULL,
                order_date TEXT NOT NULL,
                status TEXT NOT NULL,
                FOREIGN KEY(customer_id)
                    REFERENCES customers(customer_id)
            );

            CREATE TABLE IF NOT EXISTS order_items (
                item_id INTEGER PRIMARY KEY,
                order_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                unit_price REAL NOT NULL,
                FOREIGN KEY(order_id)
                    REFERENCES orders(order_id),
                FOREIGN KEY(product_id)
                    REFERENCES products(product_id)
            );
            """
        )

        # Create indexes after ensuring that all tables exist.
        _create_performance_indexes(cur)

        customer_count = cur.execute(
            "SELECT COUNT(*) FROM customers"
        ).fetchone()[0]

        if customer_count == 0:

            customers = [
                (1, "Aarav Mehta", "North", "Consumer", "2023-01-12"),
                (2, "Diya Iyer", "South", "Corporate", "2023-02-18"),
                (3, "Kabir Shah", "West", "Consumer", "2023-03-05"),
                (4, "Ananya Rao", "South", "Small Business", "2023-04-21"),
                (5, "Ishaan Nair", "East", "Corporate", "2023-05-11"),
                (6, "Meera Das", "East", "Consumer", "2023-06-19"),
                (7, "Arjun Kumar", "South", "Small Business", "2023-07-02"),
                (8, "Sara Khan", "North", "Corporate", "2023-08-14"),
                (9, "Vihaan Patel", "West", "Consumer", "2023-09-09"),
                (10, "Tara Menon", "South", "Consumer", "2023-10-27"),
            ]

            products = [
                (1, "Pulse Headphones", "Electronics", 89),
                (2, "Arc Smartwatch", "Electronics", 149),
                (3, "Everyday Backpack", "Accessories", 59),
                (4, "Studio Desk", "Furniture", 329),
                (5, "Cloud Lamp", "Home", 45),
                (6, "Sprint Sneakers", "Fashion", 110),
                (7, "Brew Coffee Kit", "Home", 72),
            ]

            orders = [
                (1001, 1, "2024-01-08", "delivered"),
                (1002, 2, "2024-01-19", "delivered"),
                (1003, 3, "2024-02-03", "returned"),
                (1004, 4, "2024-02-22", "delivered"),
                (1005, 5, "2024-03-11", "shipped"),
                (1006, 6, "2024-03-27", "delivered"),
                (1007, 7, "2024-04-06", "delivered"),
                (1008, 8, "2024-04-18", "cancelled"),
                (1009, 9, "2024-05-09", "delivered"),
                (1010, 10, "2024-05-25", "delivered"),
                (1011, 1, "2024-06-04", "delivered"),
                (1012, 2, "2024-06-16", "shipped"),
                (1013, 3, "2024-07-02", "delivered"),
                (1014, 4, "2024-07-20", "delivered"),
                (1015, 5, "2024-08-12", "returned"),
                (1016, 6, "2024-08-29", "delivered"),
                (1017, 7, "2024-09-07", "delivered"),
                (1018, 8, "2024-09-23", "delivered"),
                (1019, 9, "2024-10-10", "shipped"),
                (1020, 10, "2024-10-28", "delivered"),
                (1021, 1, "2024-11-05", "delivered"),
                (1022, 2, "2024-11-19", "delivered"),
                (1023, 3, "2024-12-02", "delivered"),
                (1024, 4, "2024-12-17", "delivered"),
                (1025, 5, "2025-01-09", "delivered"),
                (1026, 6, "2025-01-24", "shipped"),
                (1027, 7, "2025-02-08", "delivered"),
                (1028, 8, "2025-02-21", "delivered"),
                (1029, 9, "2025-03-06", "delivered"),
                (1030, 10, "2025-03-18", "delivered"),
            ]

            price = {
                product[0]: product[3]
                for product in products
            }

            items = []

            for index, order in enumerate(orders):
                first_product = (index % 7) + 1
                second_product = ((index * 3 + 2) % 7) + 1

                items.append(
                    (
                        index * 2 + 1,
                        order[0],
                        first_product,
                        (index % 4) + 1,
                        price[first_product],
                    )
                )

                if second_product != first_product:
                    items.append(
                        (
                            index * 2 + 2,
                            order[0],
                            second_product,
                            ((index + 1) % 3) + 1,
                            price[second_product],
                        )
                    )

            cur.executemany(
                "INSERT INTO customers VALUES (?, ?, ?, ?, ?)",
                customers,
            )

            cur.executemany(
                "INSERT INTO products VALUES (?, ?, ?, ?)",
                products,
            )

            cur.executemany(
                "INSERT INTO orders VALUES (?, ?, ?, ?)",
                orders,
            )

            cur.executemany(
                "INSERT INTO order_items VALUES (?, ?, ?, ?, ?)",
                items,
            )

        # Persist demo data and index definitions.
        conn.commit()

        # Ask SQLite to update its query-planner statistics.
        conn.execute("PRAGMA optimize")

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def get_schema() -> list[dict]:
    """
    Return the approved ORBIT database schema.

    This uses the in-memory schema definition and does not
    open a database connection.
    """

    return [
        {
            "table": table,
            "columns": columns.copy(),
        }
        for table, columns in SCHEMA.items()
    ]
