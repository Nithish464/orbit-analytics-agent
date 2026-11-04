
import re
import time
from typing import Any

from .database import get_connection
from .security import validate_question_intent, validate_readonly_sql


EXAMPLES = [
    "What is our total revenue?",
    "Show monthly revenue for 2024",
    "Which are the top 5 products by revenue?",
    "How many orders are there by status?",
    "Show revenue by region",
    "What is the average order value?",
    "Which customers have spent the most?",
    "Show the number of orders per month",
    "What is the average revenue?",
    "Which product generates the highest revenue?",
]


def plan_question(question: str) -> dict[str, Any]:
    """Convert a supported analytics question into a deterministic query plan."""

    q = question.lower().strip()

    year_match = re.search(r"\b(20\d{2})\b", q)
    year = year_match.group(1) if year_match else None

    limit_match = re.search(r"\btop\s+(\d+)\b", q)
    limit = int(limit_match.group(1)) if limit_match else 10
    limit = max(1, min(limit, 100))

    singular_highest = (
        any(
            term in q
            for term in (
                "highest",
                "most revenue",
                "best performing",
                "generates the most",
            )
        )
        and "product" in q
        and not limit_match
    )

    if singular_highest:
        limit = 1

    # Identify metric.
    if "average order value" in q or re.search(r"\baov\b", q):
        metric = "aov"

    elif "average revenue" in q or "mean revenue" in q:
        metric = "average_revenue"

    elif any(
        term in q
        for term in (
            "customer spend",
            "customer spending",
            "customers have spent",
            "spent the most",
            "spending",
        )
    ):
        metric = "customer_spend"

    elif any(
        term in q
        for term in (
            "order count",
            "number of orders",
            "how many orders",
            "orders per",
            "orders by",
        )
    ):
        metric = "orders"

    elif "revenue" in q or "sales" in q:
        metric = "revenue"

    else:
        metric = "overview"

    # Identify dimension.
    if "region" in q:
        dimension = "region"

    elif "product" in q:
        dimension = "product"

    elif "customer" in q:
        dimension = "customer"

    elif "status" in q:
        dimension = "status"

    elif any(
        term in q
        for term in (
            "month",
            "monthly",
            "trend",
            "over time",
        )
    ):
        dimension = "month"

    else:
        dimension = "none"

    if metric == "customer_spend":
        dimension = "customer"

    if metric in ("aov", "average_revenue"):
        dimension = "none"

    return {
        "metric": metric,
        "dimension": dimension,
        "year": year,
        "limit": limit,
        "singular_highest": singular_highest,
    }


def build_sql(plan: dict[str, Any]) -> str:
    """Build SQL using approved query templates."""

    metric = plan["metric"]
    dimension = plan["dimension"]
    year = plan.get("year")
    limit = plan.get("limit", 10)

    year_filter = ""

    if year:
        year_filter = (
            f" WHERE substr(o.order_date, 1, 4) = '{year}'"
        )

    # Total revenue.
    if metric == "revenue" and dimension == "none":
        return (
            "SELECT ROUND(SUM(oi.quantity * oi.unit_price), 2) "
            "AS total_revenue "
            "FROM orders o "
            "JOIN order_items oi ON oi.order_id = o.order_id"
            f"{year_filter}"
        )

    # Average order value.
    if metric == "aov":
        return (
            "SELECT ROUND("
            "SUM(oi.quantity * oi.unit_price) * 1.0 / "
            "COUNT(DISTINCT o.order_id), 2"
            ") AS average_order_value "
            "FROM orders o "
            "JOIN order_items oi ON oi.order_id = o.order_id"
            f"{year_filter}"
        )

    # Average revenue per order.
    if metric == "average_revenue":
        return (
            "SELECT ROUND("
            "SUM(oi.quantity * oi.unit_price) * 1.0 / "
            "COUNT(DISTINCT o.order_id), 2"
            ") AS average_revenue_per_order "
            "FROM orders o "
            "JOIN order_items oi ON oi.order_id = o.order_id"
            f"{year_filter}"
        )

    # Revenue by region.
    if metric == "revenue" and dimension == "region":
        return (
            "SELECT c.region, "
            "ROUND(SUM(oi.quantity * oi.unit_price), 2) AS revenue "
            "FROM customers c "
            "JOIN orders o ON o.customer_id = c.customer_id "
            "JOIN order_items oi ON oi.order_id = o.order_id"
            f"{year_filter} "
            "GROUP BY c.region "
            "ORDER BY revenue DESC"
        )

    # Monthly revenue.
    if metric == "revenue" and dimension == "month":
        return (
            "SELECT substr(o.order_date, 1, 7) AS month, "
            "ROUND(SUM(oi.quantity * oi.unit_price), 2) AS revenue "
            "FROM orders o "
            "JOIN order_items oi ON oi.order_id = o.order_id"
            f"{year_filter} "
            "GROUP BY month "
            "ORDER BY month"
        )

    # Revenue by product.
    if metric == "revenue" and dimension == "product":
        return (
            "SELECT p.product_name, "
            "ROUND(SUM(oi.quantity * oi.unit_price), 2) AS revenue "
            "FROM products p "
            "JOIN order_items oi ON oi.product_id = p.product_id "
            "JOIN orders o ON o.order_id = oi.order_id"
            f"{year_filter} "
            "GROUP BY p.product_id, p.product_name "
            "ORDER BY revenue DESC "
            f"LIMIT {limit}"
        )

    # Customer spending.
    if metric == "customer_spend" and dimension == "customer":
        return (
            "SELECT c.customer_name, "
            "ROUND(SUM(oi.quantity * oi.unit_price), 2) AS revenue "
            "FROM customers c "
            "JOIN orders o ON o.customer_id = c.customer_id "
            "JOIN order_items oi ON oi.order_id = o.order_id"
            f"{year_filter} "
            "GROUP BY c.customer_id, c.customer_name "
            "ORDER BY revenue DESC "
            f"LIMIT {limit}"
        )

    # Orders by status.
    if metric == "orders" and dimension == "status":
        return (
            "SELECT o.status, "
            "COUNT(DISTINCT o.order_id) AS order_count "
            "FROM orders o"
            f"{year_filter} "
            "GROUP BY o.status "
            "ORDER BY order_count DESC"
        )

    # Orders by month.
    if metric == "orders" and dimension == "month":
        return (
            "SELECT substr(o.order_date, 1, 7) AS month, "
            "COUNT(DISTINCT o.order_id) AS order_count "
            "FROM orders o"
            f"{year_filter} "
            "GROUP BY month "
            "ORDER BY month"
        )

    # Total order count.
    if metric == "orders" and dimension == "none":
        return (
            "SELECT COUNT(DISTINCT o.order_id) AS order_count "
            "FROM orders o"
            f"{year_filter}"
        )

    # General overview.
    return (
        "SELECT "
        "ROUND(SUM(oi.quantity * oi.unit_price), 2) AS total_revenue, "
        "COUNT(DISTINCT o.order_id) AS total_orders "
        "FROM orders o "
        "JOIN order_items oi ON oi.order_id = o.order_id"
        f"{year_filter}"
    )


def run_query(
    sql: str,
) -> tuple[list[str], list[dict[str, Any]]]:
    """Validate and execute a read-only SQL query."""

    # IMPORTANT: validator returns (is_valid, validated_sql_or_error).
    is_valid, validation_result = validate_readonly_sql(sql)

    if not is_valid:
        raise ValueError(str(validation_result))

    safe_sql = validation_result

    connection = get_connection(readonly=True)

    try:
        connection.execute("PRAGMA query_only = ON")

        cursor = connection.execute(safe_sql)

        columns = [
            description[0]
            for description in (cursor.description or [])
        ]

        fetched_rows = cursor.fetchmany(100)
        rows = [dict(row) for row in fetched_rows]

        return columns, rows

    finally:
        connection.close()


def make_chart(
    columns: list[str],
    rows: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Create a bar chart configuration when suitable."""

    if not rows or len(columns) < 2:
        return None

    numeric_columns = [
        column
        for column in columns
        if all(
            isinstance(row.get(column), (int, float))
            and not isinstance(row.get(column), bool)
            for row in rows
        )
    ]

    if not numeric_columns:
        return None

    x_key = next(
        (
            column
            for column in columns
            if column not in numeric_columns
        ),
        None,
    )

    if x_key is None:
        return None

    y_key = numeric_columns[0]

    label = (
        "Order Count"
        if "order_count" in y_key
        else "Revenue"
    )

    return {
        "type": "bar",
        "xKey": x_key,
        "yKey": y_key,
        "label": label,
        "data": rows,
    }


def _money(value: Any) -> str:
    """Format a numeric value."""

    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return str(value)


def make_answer(
    question: str,
    plan: dict[str, Any],
    rows: list[dict[str, Any]],
) -> str:
    """Generate business insights from query results."""

    if not rows:
        return "No matching records were found for this question."

    metric = plan["metric"]
    dimension = plan["dimension"]
    first = rows[0]

    # Total revenue.
    if metric == "revenue" and dimension == "none":
        value = first.get("total_revenue", 0)

        return (
            f"Total recorded revenue is {_money(value)} "
            "across the selected dataset."
        )

    # Average order value.
    if metric == "aov":
        value = first.get("average_order_value", 0)

        return (
            f"The average order value is {_money(value)}."
        )

    # Average revenue per order.
    if metric == "average_revenue":
        value = first.get("average_revenue_per_order", 0)

        return (
            f"Average revenue per order is {_money(value)}. "
            "This is calculated as total revenue divided by "
            "the number of distinct orders."
        )

    # Product revenue.
    if metric == "revenue" and dimension == "product":

        if plan.get("singular_highest"):
            return (
                f"{first['product_name']} generates the highest "
                f"revenue at {_money(first['revenue'])}."
            )

        if len(rows) == 1:
            return (
                f"{first['product_name']} leads product revenue "
                f"with {_money(first['revenue'])}."
            )

        second = rows[1]

        return (
            f"{first['product_name']} leads product revenue with "
            f"{_money(first['revenue'])}, followed by "
            f"{second['product_name']} with "
            f"{_money(second['revenue'])}. "
            f"Returned {len(rows)} products ranked by revenue."
        )

    # Customer spending.
    if metric == "customer_spend":
        if len(rows) == 1:
            return (
                f"{first['customer_name']} is the highest-spending "
                f"customer with {_money(first['revenue'])}."
            )

        second = rows[1]

        return (
            f"{first['customer_name']} is the highest-spending "
            f"customer with {_money(first['revenue'])}, followed by "
            f"{second['customer_name']} with "
            f"{_money(second['revenue'])}. "
            f"Returned {len(rows)} customer records."
        )

    # Revenue by region.
    if metric == "revenue" and dimension == "region":
        total = sum(
            float(row.get("revenue", 0))
            for row in rows
        )

        highest = float(first.get("revenue", 0))
        percentage = highest / total * 100 if total else 0

        return (
            f"{first['region']} leads regional revenue with "
            f"{_money(highest)}, accounting for "
            f"{percentage:.1f}% of the revenue returned by this query."
        )

    # Monthly revenue.
    if metric == "revenue" and dimension == "month":
        values = [
            float(row.get("revenue", 0))
            for row in rows
        ]

        highest = max(values)

        winners = [
            row["month"]
            for row in rows
            if float(row.get("revenue", 0)) == highest
        ]

        if len(winners) == 1:
            return (
                f"The highest revenue month was {winners[0]} "
                f"with {_money(highest)}. "
                f"Returned {len(rows)} monthly data points."
            )

        return (
            f"The highest monthly revenue was {_money(highest)}, "
            f"tied across {len(winners)} months. "
            f"Returned {len(rows)} monthly data points."
        )

    # Orders by status.
    if metric == "orders" and dimension == "status":
        total = sum(
            int(row.get("order_count", 0))
            for row in rows
        )

        highest = int(first.get("order_count", 0))

        winners = [
            row["status"]
            for row in rows
            if int(row.get("order_count", 0)) == highest
        ]

        percentage = highest / total * 100 if total else 0

        if len(winners) == 1:
            return (
                f"{first['status'].capitalize()} is the most common "
                f"order status with {highest} orders "
                f"({percentage:.1f}% of all returned orders)."
            )

        return (
            f"The highest order count is {highest}, tied across "
            f"{len(winners)} statuses."
        )

    # Orders by month.
    if metric == "orders" and dimension == "month":
        values = [
            int(row.get("order_count", 0))
            for row in rows
        ]

        highest = max(values)

        winners = [
            row["month"]
            for row in rows
            if int(row.get("order_count", 0)) == highest
        ]

        if len(winners) == 1:
            return (
                f"The highest monthly order count was {highest} "
                f"in {winners[0]}. "
                f"Returned {len(rows)} monthly data points."
            )

        return (
            f"The highest monthly order count was {highest}, "
            f"tied across {len(winners)} months. "
            f"Returned {len(rows)} monthly data points."
        )

    # Total order count.
    if metric == "orders" and dimension == "none":
        return (
            f"The total number of recorded orders is "
            f"{first.get('order_count', 0)}."
        )

    # General overview.
    if metric == "overview":
        revenue = first.get("total_revenue", 0)
        orders = first.get("total_orders", 0)

        return (
            f"Dataset overview: total revenue is {_money(revenue)} "
            f"across {orders} orders."
        )

    return (
        f"Returned {len(rows)} records for your analytics question."
    )


def execute_workflow(question: str) -> dict[str, Any]:
    """Execute the ORBIT deterministic analytics workflow."""

    start_time = time.perf_counter()
    steps = []

    try:
        # Step 1: Validate question.
        validate_question_intent(question)

        plan = plan_question(question)

        steps.append({
            "name": "Planner",
            "status": "complete",
            "detail": (
                f"Detected metric={plan['metric']}, "
                f"dimension={plan['dimension']}."
            ),
        })

        # Step 2: Build SQL.
        sql = build_sql(plan)

        steps.append({
            "name": "SQL Builder",
            "status": "complete",
            "detail": (
                "Generated a read-only query from approved query templates."
            ),
        })

        # Step 3: Validate SQL.
        # IMPORTANT: validator returns a tuple.
        is_valid, validation_result = validate_readonly_sql(sql)

        if not is_valid:
            raise ValueError(str(validation_result))

        steps.append({
            "name": "SQL Safety Critic",
            "status": "complete",
            "detail": (
                "Single SELECT query, approved tables, "
                "no comments or write operations."
            ),
        })

        # Step 4: Execute query.
        # run_query validates again and extracts the SQL string.
        columns, rows = run_query(sql)

        steps.append({
            "name": "Query Executor",
            "status": "complete",
            "detail": (
                f"Executed safely and returned {len(rows)} row(s)."
            ),
        })

        # Step 5: Generate business insights.
        answer = make_answer(question, plan, rows)
        chart = make_chart(columns, rows)

        steps.append({
            "name": "Business Analyst",
            "status": "complete",
            "detail": (
                "Generated business insights from returned records."
            ),
        })

        duration_ms = round(
            (time.perf_counter() - start_time) * 1000,
            2,
        )

        return {
            "question": question,
            "answer": answer,
            "sql": sql,
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "chart": chart,
            "steps": steps,
            "duration_ms": duration_ms,
            "mode": "deterministic-demo",
        }

    except Exception:
        raise
