
import re

from .database import SCHEMA


# Reject destructive database-related requests.
DANGEROUS_INTENT = re.compile(
    r"\b("
    r"insert|update|delete|drop|alter|create|truncate|replace|"
    r"attach|detach|vacuum|pragma|grant|revoke|"
    r"execute|exec"
    r")\b",
    re.IGNORECASE,
)


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


# SQL operations that must not appear in generated SQL.
FORBIDDEN_SQL = re.compile(
    r"\b("
    r"INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|"
    r"TRUNCATE|ATTACH|DETACH|PRAGMA|VACUUM|REINDEX|"
    r"ANALYZE|GRANT|REVOKE|EXEC|EXECUTE|INTO|"
    r"LOAD_EXTENSION"
    r")\b",
    re.IGNORECASE,
)


def validate_question_intent(question: str):
    """
    Validate a natural-language question before query planning.
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

    if DANGEROUS_INTENT.search(q):
        raise ValueError(
            "Only read-only business analytics questions are allowed."
        )

    if not ANALYTICS_TERMS.search(q):
        raise ValueError(
            "Unsupported question. Please ask about revenue, orders, "
            "customers, products, regions, or monthly trends."
        )

    return True


def validate_readonly_sql(sql: str):
    """
    Validate generated read-only SQL against the approved schema.

    This is a basic safeguard for ORBIT's fixed query templates,
    not a complete SQL parser.
    """

    if not sql or not sql.strip():
        return False, "Query is empty."

    s = sql.strip()

    # Allow one optional trailing semicolon.
    if s.endswith(";"):
        s = s[:-1].strip()

    # Reject multiple SQL statements.
    if ";" in s:
        return False, "Multiple SQL statements are not allowed."

    # Reject SQL comments.
    if "--" in s or "/*" in s or "*/" in s:
        return False, "SQL comments are not allowed."

    # Only SELECT statements are allowed.
    if not re.match(r"(?is)^SELECT\b", s):
        return False, "Only SELECT queries are permitted."

    # Reject restricted SQL operations.
    if FORBIDDEN_SQL.search(s):
        return False, "Query contains a restricted SQL operation."

    # Extract tables used in FROM and JOIN clauses.
    tables = re.findall(
        r"\b(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*)",
        s,
        re.IGNORECASE,
    )

    if not tables:
        return False, "Query must reference an approved table."

    approved_tables = {
        table.lower()
        for table in SCHEMA.keys()
    }

    for table in tables:
        if table.lower() not in approved_tables:
            return False, (
                f"Query references an unapproved table: {table}"
            )

    # Add a default result limit if missing.
    if not re.search(r"\bLIMIT\s+\d+\b", s, re.IGNORECASE):
        s += " LIMIT 100"

    return True, s
