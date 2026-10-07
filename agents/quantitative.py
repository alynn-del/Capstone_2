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
    message = client.chat.completions.create(
        model="gemini-3.6-flash",
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

    return {
        "answer": "Query executed successfully.",
        "sql": sql,
        "rows": rows,
        "columns": cols,
        "validation": "PASSED",
        "input_tokens": sql_result["input_tokens"],
        "output_tokens": sql_result["output_tokens"],
    }

def test_quantitative_agent():
    test_queries = [
        "Show me monthly revenue trends",
        "What is our customer churn rate?",
        "Compare Q4 performance across regions",
    ]

    for number, user_query in enumerate(test_queries, start=1):
        print(f"\n{'=' * 70}")
        print(f"TEST {number}: {user_query}")
        print("=" * 70)

        result = run(user_query)

        print(f"\nValidation: {result.get('validation')}")
        print(f"Generated SQL: {result.get('sql')}")
        print(f"Rows returned: {len(result.get('rows', []))}")
        print(f"Input tokens: {result.get('input_tokens', 0)}")
        print(f"Output tokens: {result.get('output_tokens', 0)}")

        if result.get("columns"):
            print(f"Columns: {result['columns']}")

        if result.get("rows"):
            print("First five rows:")
            for row in result["rows"][:5]:
                print(row)

        print(f"\nAgent interpretation:\n{result.get('answer')}")


if __name__ == "__main__":
    test_quantitative_agent()