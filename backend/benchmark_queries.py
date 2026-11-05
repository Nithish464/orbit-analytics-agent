
"""
ORBIT Analytics Agent
Database Query Performance Benchmark

Measures execution time for frequently used SQLite queries.
Uses a read-only database connection.
"""

import time
import statistics

from app.database import get_connection


# Number of benchmark iterations per query.
ITERATIONS = 100


TEST_QUERIES = [
    {
        "name": "Year Filter",
        "sql": """
            SELECT COUNT(*)
            FROM orders
            WHERE substr(order_date, 1, 4) = ?
        """,
        "params": ("2024",),
    },
    {
        "name": "Customer JOIN",
        "sql": """
            SELECT COUNT(*)
            FROM orders o
            JOIN customers c
                ON c.customer_id = o.customer_id
            WHERE c.customer_id = ?
        """,
        "params": (1,),
    },
    {
        "name": "Order JOIN",
        "sql": """
            SELECT COUNT(*)
            FROM order_items oi
            JOIN orders o
                ON o.order_id = oi.order_id
            WHERE o.order_id = ?
        """,
        "params": (1001,),
    },
    {
        "name": "Product JOIN",
        "sql": """
            SELECT COUNT(*)
            FROM order_items oi
            JOIN products p
                ON p.product_id = oi.product_id
            WHERE p.product_id = ?
        """,
        "params": (1,),
    },
]


def benchmark_query(connection, query):
    """
    Execute one query repeatedly and calculate timing statistics.
    """

    sql = query["sql"]
    params = query["params"]

    # Warm-up execution.
    connection.execute(sql, params).fetchone()

    execution_times = []

    for _ in range(ITERATIONS):
        start_time = time.perf_counter()

        connection.execute(
            sql,
            params,
        ).fetchone()

        elapsed_ms = (
            time.perf_counter() - start_time
        ) * 1000

        execution_times.append(elapsed_ms)

    return {
        "average_ms": statistics.mean(execution_times),
        "minimum_ms": min(execution_times),
        "maximum_ms": max(execution_times),
        "median_ms": statistics.median(execution_times),
    }


def run_benchmark():
    """
    Run all database performance benchmarks.
    """

    connection = get_connection(readonly=True)

    try:
        print("\n" + "=" * 60)
        print("       ORBIT DATABASE PERFORMANCE BENCHMARK")
        print("=" * 60)

        print(f"\nIterations per query: {ITERATIONS}")
        print("Database mode: READ ONLY")

        results = []

        for query in TEST_QUERIES:
            print("\n" + "-" * 60)
            print(f"Query: {query['name']}")
            print("-" * 60)

            result = benchmark_query(
                connection,
                query,
            )

            results.append({
                "name": query["name"],
                **result,
            })

            print(
                f"Average execution time : "
                f"{result['average_ms']:.4f} ms"
            )

            print(
                f"Minimum execution time : "
                f"{result['minimum_ms']:.4f} ms"
            )

            print(
                f"Maximum execution time : "
                f"{result['maximum_ms']:.4f} ms"
            )

            print(
                f"Median execution time  : "
                f"{result['median_ms']:.4f} ms"
            )

        print("\n" + "=" * 60)
        print("                 BENCHMARK SUMMARY")
        print("=" * 60)

        print(
            f"{'Query':<20}"
            f"{'Average (ms)':>18}"
            f"{'Minimum (ms)':>18}"
        )

        print("-" * 60)

        for result in results:
            print(
                f"{result['name']:<20}"
                f"{result['average_ms']:>18.4f}"
                f"{result['minimum_ms']:>18.4f}"
            )

        print("-" * 60)
        print("\nBenchmark completed successfully.")

    finally:
        connection.close()


if __name__ == "__main__":
    try:
        run_benchmark()

    except Exception as error:
        print("\nBenchmark failed.")
        print(f"Error: {error}")
        raise
