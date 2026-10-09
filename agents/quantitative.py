import sqlite3
import os
import re
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()

client = OpenAI(
        api_key=os.getenv("GEMINI_API_KEY"),
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
    )

SCHEMA_CONTEXT = """
Available tables:
- sales(id, region, product, revenue, date, units_sold)
- customers(id, name, industry, churn_date, satisfaction_score)
- employees(id, department, satisfaction_score, tenure_years)
"""

#----------Validating SQL query before calling database-------------
    # this is separate from validator.py because it needs to be called before the query is executed at all
def validate_sql(query: str) -> dict:

    sql = (query or "").strip()

    #-------Basic catch for empty query--------
    if not sql:
        return {"valid": False, "reason": "SQL query is empty."}

    #------Make sure the query uses a from statement specifying the table------------
    sql = re.sub(r"\s*```\s*$", "", sql).strip()
    if not re.search(r"\bFROM\b", sql, flags=re.IGNORECASE):
        return {
            "valid": False,
            "reason": "Read-only queries must include a FROM clause.",
        }

    #------Check for multiple SQL queries--------
    if sql.endswith(";"):
        sql_stripped = sql[:-1].strip()
        if ";" in sql_stripped:
                return {
                    "valid": False,
                    "reason": "Multiple SQL statements are not permitted.",
                }

    # ------Check for blocked keywords--------
    blocked = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE", "REPLACE", "REINDEX", "REMAME", "MERGE", "GRANT", "REVOKE", "COMMIT", "ROLLBACK"]
    for word in blocked:
        if word in sql.upper():
            return {"valid": False, "reason": f"Blocked keyword: {word}"}
    if not sql.strip().upper().startswith(("SELECT", "WITH")):
        return {"valid": False, "reason": "SQL queries must start with SELECT or WITH."}
    
    return {"valid": True, "reason": "Read-only SQL query is valid.", "sql":sql}

#------------------Helper function to clean SQL formatting-----------------
def clean_sql(raw_sql: str) -> str:
    sql = (raw_sql or "").strip()

    sql = re.sub(
        r"^\s*```(?:sql)?\s*",
        "",
        sql,
        flags=re.IGNORECASE,
    )

    sql = re.sub(
        r"\s*```\s*$",
        "",
        sql,
    ).strip()

    return sql

def generate_sql(query: str) -> dict:

    # --- NL→SQL prompt design -----------------------------------------------
        # SCHEMA_CONTEXT injected first → model sees exact tables/columns before the
        #   task, so it can only reference real fields (grounds the generation).
        # "one complete executable SQLite query" → dialect-specific + runnable as-is;
        #   downstream code executes it directly with no editing.
        # "no Markdown fences or explanations" → output must be raw SQL
        # "must include the correct FROM table" → guards the most common failure mode
        #   (valid-looking SQL with no/wrong source table).
        # "only tables and columns in the schema" → blocks hallucinated fields that
        #   would throw at execution time.
        # max_tokens=512 → room for a multi-clause query (JOINs/GROUP BY) while still capping cost.
    # ------------------------------------------------------------------------
    message = client.chat.completions.create(
        model="gemini-3.5-flash-lite",
        max_tokens=512,
        messages=[
            {
                "role": "user",
                "content": (
                    f"{SCHEMA_CONTEXT}\n\n"
                    f"Generate SQL for: {query}\n\n"
                    "Return one complete executable SQLite query. "
                    "Do not include Markdown fences or explanations. "
                    "Every query must include the correct FROM table. "
                    "Use only tables and columns listed in the schema."
                ),
            }
        ],
    )

    raw_sql = message.choices[0].message.content or ""
    sql = clean_sql(raw_sql)

    return {
        "sql": sql,
        "input_tokens": getattr(message.usage, "prompt_tokens", 0),
        "output_tokens": getattr(message.usage, "completion_tokens", 0),
    }


def run(query: str) -> dict:
    sql_result = generate_sql(query)
    raw_sql = sql_result["sql"]
    validation = validate_sql(raw_sql)

    if not validation["valid"]:
        return {
            "answer": f"Query blocked: {validation['reason']}",
            "sql": raw_sql,
            "rows": [],
            "validation": "FAILED",
            "input_tokens": sql_result["input_tokens"],
            "output_tokens": sql_result["output_tokens"],
        }

    sql = validation.get("sql", raw_sql)

    db_path = "./data/documents/database.sqlite"

    with sqlite3.connect(
        f"file:{db_path}?mode=ro",
        uri=True,
    ) as conn:
        conn.execute("PRAGMA query_only = ON")

        cursor = conn.cursor()
        cursor.execute(sql)
        rows = cursor.fetchall()
        cols = [description[0] for description in cursor.description]

    #-----------------Generate interpretation of the results--------------

    # --- Result interpretation prompt design ----------------------------
        # Pass question + SQL + columns + rows together so the model explains the
        #   actual returned data in the context of what was asked (not a guess).
        # Including the SQL and column names helps the interpretation be focused on real
        #   fields, so numbers get labeled correctly instead of mislabeled.
        # "clearly and concisely" → this is the user-facing synopsis; keep it short.
        # "no markdown syntax" → output is printed raw to the CLI, where stray *, #,
        #   or | would show as literal characters, not formatting.
        # max_tokens=204 → a few sentences of plain-text summary; caps cost.
    # ------------------------------------------------------------------------
    interpretation = client.chat.completions.create(
        model="gemini-3.5-flash-lite",
        max_tokens=204,
        messages=[
            {
                "role": "user",
                "content": (
                    f"User question: {query}\n\n"
                    f"SQL query: {sql}\n\n"
                    f"Columns: {cols}\n"
                    f"SQL output: {rows}\n\n"
                    "Interpret these results clearly and concisely. Output should have no markdown syntax."
                ),
            }
        ],
    )
    answer = interpretation.choices[0].message.content.strip()

    return {
        "answer": answer,
        "sql": sql,
        "rows": rows,
        "columns": cols,
        "validation": "PASSED",
        "input_tokens": sql_result["input_tokens"],
        "output_tokens": sql_result["output_tokens"],
    }