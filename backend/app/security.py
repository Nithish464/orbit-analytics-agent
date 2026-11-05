
import re

import sqlglot
from sqlglot import exp
from sqlglot.optimizer.scope import traverse_scope

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
MAX_SQL_LENGTH = 10_000

FORBIDDEN_FUNCTIONS = {
    "load_extension",
    "readfile",
    "writefile",
}


def validate_question_intent(question: str) -> bool:
    """Validate a natural-language analytics question."""

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
    """Detect SQL comments outside quoted strings and identifiers."""

    quote = None
    index = 0
    length = len(sql)

    while index < length:
        char = sql[index]

        if quote is not None:
            if char == quote:
                if (
                    index + 1 < length
                    and sql[index + 1] == quote
                ):
                    index += 2
                    continue

                quote = None

            elif char == "\\" and quote in ("'", '"', "`"):
                index += 2
                continue

            index += 1
            continue

        if char in ("'", '"', "`"):
            quote = char
            index += 1
            continue

        if char == "[":
            quote = "]"
            index += 1
            continue

        if sql.startswith("--", index):
            return True

        if sql.startswith("/*", index):
            return True

        index += 1

    return False


def _get_approved_schema() -> dict[str, set[str]]:
    """Normalize the approved schema for case-insensitive validation."""

    return {
        table_name.lower(): {
            column.lower()
            for column in columns
        }
        for table_name, columns in SCHEMA.items()
    }


def _get_source_columns(
    source,
    approved_tables: dict[str, set[str]],
) -> set[str]:
    """
    Resolve available columns for a source in a SQL scope.

    Physical tables use the approved database schema.
    CTEs and derived tables expose their SELECT output names.
    """

    if isinstance(source, exp.Table):
        table_name = source.name.lower()

        if source.db or source.catalog:
            raise ValueError(
                "External database references are not allowed."
            )

        if table_name not in approved_tables:
            raise ValueError(
                f"Query references an unapproved table: {source.name}"
            )

        return approved_tables[table_name]

    # SQLGlot Scope objects represent CTEs and derived queries.
    if hasattr(source, "expression"):
        expression = source.expression

        if not isinstance(expression, exp.Select):
            raise ValueError(
                "Unsupported derived SQL source."
            )

        output_columns = set()

        for selected_expression in expression.expressions:
            if isinstance(selected_expression, exp.Star):
                raise ValueError(
                    "Wildcard columns in CTEs and derived tables "
                    "are not supported. Specify columns explicitly."
                )

            if isinstance(selected_expression, exp.Column):
                if selected_expression.is_star:
                    raise ValueError(
                        "Wildcard columns in derived queries "
                        "are not supported."
                    )

            output_name = selected_expression.alias_or_name

            if not output_name:
                raise ValueError(
                    "Every derived query column must have a name."
                )

            output_columns.add(output_name.lower())

        return output_columns

    raise ValueError("Unable to resolve SQL query source.")


def _validate_scopes(
    tree: exp.Expression,
    approved_tables: dict[str, set[str]],
) -> None:
    """
    Validate table sources and column references scope by scope.

    Correlated references can resolve against parent scopes.
    """

    scopes = list(traverse_scope(tree))

    if not scopes:
        raise ValueError(
            "Unable to resolve SQL query scopes."
        )

    scope_sources = {}
    base_table_count = 0

    for scope in scopes:
        current_sources = {}

        for alias, source in scope.sources.items():
            source_columns = _get_source_columns(
                source,
                approved_tables,
            )

            current_sources[alias.lower()] = (
                source,
                source_columns,
            )

            if isinstance(source, exp.Table):
                base_table_count += 1

        scope_sources[id(scope)] = current_sources

    if base_table_count == 0:
        raise ValueError(
            "Query must reference an approved database table."
        )

    # Validate columns independently within each scope.
    for scope in scopes:
        current_sources = scope_sources[id(scope)]

        select_aliases = {
            expression.alias.lower()
            for expression in scope.expression.expressions
            if isinstance(expression, exp.Alias)
        }

        for column in scope.columns:
            column_name = column.name.lower()

            # Validate qualified references.
            if column.table:
                qualifier = column.table.lower()

                current_scope = scope
                resolved = False

                while current_scope is not None:
                    sources = scope_sources.get(
                        id(current_scope),
                        {},
                    )

                    if qualifier in sources:
                        _, source_columns = sources[qualifier]

                        if (
                            not column.is_star
                            and column_name not in source_columns
                        ):
                            raise ValueError(
                                f"Unapproved column: {column.name}"
                            )

                        resolved = True
                        break

                    current_scope = current_scope.parent

                if not resolved:
                    raise ValueError(
                        f"Unknown table alias: {column.table}"
                    )

                continue

            # Wildcards are allowed for physical table queries.
            if column.is_star:
                continue

            # Allow SELECT aliases.
            if column_name in select_aliases:
                continue

            matching_sources = [
                alias
                for alias, (_, source_columns)
                in current_sources.items()
                if column_name in source_columns
            ]

            if len(matching_sources) > 1:
                raise ValueError(
                    f"Ambiguous column: {column.name}. "
                    "Please qualify it with a table name or alias."
                )

            if len(matching_sources) == 1:
                continue

            # Check parent scopes for correlated references.
            parent_scope = scope.parent
            resolved = False

            while parent_scope is not None:
                parent_sources = scope_sources.get(
                    id(parent_scope),
                    {},
                )

                parent_matches = [
                    alias
                    for alias, (_, source_columns)
                    in parent_sources.items()
                    if column_name in source_columns
                ]

                if len(parent_matches) > 1:
                    raise ValueError(
                        f"Ambiguous correlated column: {column.name}"
                    )

                if len(parent_matches) == 1:
                    resolved = True
                    break

                parent_scope = parent_scope.parent

            if not resolved:
                raise ValueError(
                    f"Unapproved column: {column.name}"
                )


def _get_function_names(node: exp.Func) -> set[str]:
    """
    Extract function names from SQLGlot function expressions.

    Anonymous functions such as SQLite readfile(), writefile()
    and load_extension() need node.name rather than only sql_name().
    """

    names = set()

    try:
        sql_name = node.sql_name()
        if sql_name:
            names.add(str(sql_name).lower())
    except (AttributeError, ValueError):
        pass

    try:
        function_name = node.name
        if function_name:
            names.add(str(function_name).lower())
    except (AttributeError, ValueError):
        pass

    return names


def validate_readonly_sql(sql: str) -> tuple[bool, str]:
    """
    Validate SQL using SQLGlot AST and scope traversal.

    Security rules:
    - Only one SELECT statement.
    - SQL comments are rejected.
    - Only approved physical database tables.
    - Only approved database columns.
    - Scope-aware alias validation.
    - CTE and derived query output validation.
    - Correlated column resolution against parent scopes.
    - Ambiguous unqualified columns are rejected.
    - Write operations are rejected.
    - External database references are rejected.
    - Dangerous functions are rejected throughout the AST.
    - Maximum result limit is 100 rows.
    - SQL length is bounded.
    """

    if not isinstance(sql, str) or not sql.strip():
        return False, "Query is empty."

    sql = sql.strip()

    if len(sql) > MAX_SQL_LENGTH:
        return False, (
            f"SQL query is too long. Maximum length is "
            f"{MAX_SQL_LENGTH} characters."
        )

    if _contains_sql_comment(sql):
        return False, "SQL comments are not permitted."

    try:
        statements = sqlglot.parse(sql, read="sqlite")

    except sqlglot.errors.ParseError:
        return False, "Invalid SQL syntax."

    if len(statements) != 1 or statements[0] is None:
        return False, "Only one SQL statement is allowed."

    tree = statements[0]

    if not isinstance(tree, exp.Select):
        return False, "Only SELECT queries are permitted."

    # Reject dangerous SQL constructs throughout the AST,
    # including nested SELECTs and CTEs.
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

        if isinstance(node, exp.Func):
            function_names = _get_function_names(node)

            if function_names.intersection(FORBIDDEN_FUNCTIONS):
                return False, (
                    "Query contains a restricted SQL function."
                )

    approved_tables = _get_approved_schema()

    try:
        _validate_scopes(tree, approved_tables)

    except ValueError as exc:
        return False, str(exc)

    # Enforce maximum result limit on the outer query.
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
            return False, "Invalid LIMIT value."

        if requested_limit < 1:
            return False, "LIMIT must be at least 1."

        if requested_limit > MAX_LIMIT:
            return False, (
                f"LIMIT cannot exceed {MAX_LIMIT} rows."
            )

    validated_sql = tree.sql(dialect="sqlite")

    return True, validated_sql
