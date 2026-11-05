
import re

import sqlglot
from sqlglot import exp

from .database import SCHEMA


# Recognized business analytics terms.
ANALYTICS_TERMS = re.compile(
    r"\b("
    r"revenue|sales|income|turnover|"
    r"average order|average|aov|"
    r"customer|customers|"
    r"order|orders|"
    r"product|products|"
    r"category|categories|"
    r"item|items|"
    r"region|regions|"
    r"status|"
    r"month|monthly|year|annual|"
    r"trend|"
    r"dataset|data|summary|overview|"
    r"total|count|number|"
    r"top|highest|most|spent|spending|"
    r"show|list|compare"
    r")\b",
    re.IGNORECASE,
)


MAX_LIMIT = 100

FORBIDDEN_FUNCTIONS = {
    "load_extension",
    "readfile",
    "writefile",
}


def validate_question_intent(question: str) -> bool:
    """
    Validate a natural-language analytics question.
    """

    if not question or not question.strip():
        raise ValueError("Question cannot be empty.")

    q = question.strip()

    if len(q) < 3:
        raise ValueError(
            "Please enter a meaningful analytics question."
        )

    if len(q) > 500:
        raise ValueError(
            "Question is too long. Maximum length is 500 characters."
        )

    if not ANALYTICS_TERMS.search(q):
        raise ValueError(
            "Unsupported question. Please ask about revenue, orders, "
            "customers, products, regions, or monthly trends."
        )

    return True


def _contains_sql_comment(sql: str) -> bool:
    """
    Detect SQL comments outside quoted strings and identifiers.

    Rejects:
        -- line comments
        /* block comments */

    Does not reject comment-like text inside quoted values.
    """

    quote = None
    index = 0
    length = len(sql)

    while index < length:
        char = sql[index]

        # Inside a quoted string or identifier.
        if quote is not None:

            if char == quote:

                # Handle escaped/doubled quote characters.
                if (
                    index + 1 < length
                    and sql[index + 1] == quote
                ):
                    index += 2
                    continue

                quote = None

            elif char == "\\" and quote in ("'", '"', "`"):

                # Handle backslash-escaped characters.
                index += 2
                continue

            index += 1
            continue

        # Detect opening quotes and quoted identifiers.
        if char in ("'", '"', "`"):
            quote = char
            index += 1
            continue

        # SQLite bracket-quoted identifiers.
        if char == "[":
            quote = "]"
            index += 1
            continue

        # Reject SQL line comments.
        if sql.startswith("--", index):
            return True

        # Reject SQL block comments.
        if sql.startswith("/*", index):
            return True

        index += 1

    return False


def validate_readonly_sql(sql: str) -> tuple[bool, str]:
    """
    Validate SQL using SQLGlot AST parsing.

    Security rules:
    - Only one SELECT statement.
    - SQL comments are rejected.
    - Only approved database tables.
    - Only approved database columns.
    - SELECT aliases are supported.
    - Write operations are rejected.
    - External database references are rejected.
    - Dangerous functions are rejected.
    - Maximum result limit is 100 rows.

    Returns:
        (True, validated_sql) when valid.
        (False, error_message) when invalid.
    """

    if not sql or not sql.strip():
        return False, "Query is empty."

    # Reject comments before SQLGlot parsing.
    # SQLGlot may otherwise silently ignore comments.
    if _contains_sql_comment(sql):
        return False, "SQL comments are not permitted."

    try:
        statements = sqlglot.parse(sql, read="sqlite")

    except sqlglot.errors.ParseError:
        return False, "Invalid SQL syntax."

    if len(statements) != 1 or statements[0] is None:
        return False, "Only one SQL statement is allowed."

    tree = statements[0]

    # Only SELECT statements are permitted.
    if not isinstance(tree, exp.Select):
        return False, "Only SELECT queries are permitted."

    # Explicitly reject dangerous SQL constructs.
    forbidden_nodes = (
        exp.Insert,
        exp.Update,
        exp.Delete,
        exp.Drop,
        exp.Create,
        exp.Command,
        exp.Pragma,
        exp.Transaction,
        exp.Merge,
        exp.Into,
    )

    for node in tree.walk():

        if isinstance(node, forbidden_nodes):
            return False, (
                "Query contains a restricted SQL operation."
            )

        # Reject dangerous functions.
        if isinstance(node, exp.Func):
            function_name = node.sql_name().lower()

            if function_name in FORBIDDEN_FUNCTIONS:
                return False, (
                    "Query contains a restricted SQL function."
                )

    # Extract all referenced tables.
    tables = list(tree.find_all(exp.Table))

    if not tables:
        return False, (
            "Query must reference an approved table."
        )

    # Build approved schema lookup.
    approved_tables = {
        table_name.lower(): {
            column.lower()
            for column in columns
        }
        for table_name, columns in SCHEMA.items()
    }

    # Validate table names and reject external database references.
    for table in tables:

        table_name = table.name.lower()

        if table_name not in approved_tables:
            return False, (
                f"Query references an unapproved table: {table.name}"
            )

        if table.db or table.catalog:
            return False, (
                "External database references are not allowed."
            )

    # Build table alias mapping.
    aliases = {}

    for table in tables:
        aliases[table.alias_or_name.lower()] = table.name.lower()

    # Collect SELECT aliases.
    select_aliases = {
        expression.alias.lower()
        for expression in tree.expressions
        if isinstance(expression, exp.Alias)
    }

    # Validate every referenced column.
    for column in tree.find_all(exp.Column):

        column_name = column.name.lower()

        # Allow wildcard expressions.
        if column_name == "*":
            continue

        # Allow aliases in GROUP BY and ORDER BY.
        if (
            not column.table
            and column_name in select_aliases
        ):
            continue

        # Validate explicitly qualified columns.
        if column.table:

            table_name = aliases.get(
                column.table.lower()
            )

            if table_name is None:
                return False, (
                    f"Unknown table alias: {column.table}"
                )

            if column_name not in approved_tables[table_name]:
                return False, (
                    f"Unapproved column: {column.name}"
                )

        else:
            # Resolve unqualified columns against approved tables.
            matching_tables = [
                table_name
                for table_name in set(aliases.values())
                if column_name in approved_tables[table_name]
            ]

            if not matching_tables:
                return False, (
                    f"Unapproved column: {column.name}"
                )

    # Enforce the maximum result limit.
    limit_node = tree.args.get("limit")

    if limit_node is None:

        tree = tree.limit(MAX_LIMIT)

    else:

        limit_value = limit_node.expression

        if not isinstance(limit_value, exp.Literal):
            return False, (
                "LIMIT must be a numeric constant."
            )

        if limit_value.is_string:
            return False, (
                "LIMIT must be numeric."
            )

        try:
            requested_limit = int(limit_value.this)

        except (TypeError, ValueError):
            return False, (
                "Invalid LIMIT value."
            )

        if requested_limit < 1:
            return False, (
                "LIMIT must be at least 1."
            )

        if requested_limit > MAX_LIMIT:
            return False, (
                f"LIMIT cannot exceed {MAX_LIMIT} rows."
            )

    # Return normalized SQLite SQL.
    validated_sql = tree.sql(dialect="sqlite")

    return True, validated_sql
