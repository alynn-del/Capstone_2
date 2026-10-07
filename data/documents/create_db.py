# Creating the dummy database using semi-random data creation
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

random.seed(42)

DB_PATH = Path("data/documents/database.sqlite")

# -------------------arbitrary dummy data------------------
regions = ["Northeast", "Southeast", "Midwest", "Southwest", "West"]
products = ["Analytics Platform", "Cloud Services", "Cybersecurity", "Consulting", "AI Solutions"]
industries = ["Healthcare", "Financial Services", "Retail", "Manufacturing", "Technology"]
departments = ["Consulting", "Audit", "Tax", "Technology", "Human Resources", "Finance"]
first_names = ["Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Avery", "Cameron"]
last_names = ["Smith", "Johnson", "Williams", "Brown", "Davis", "Miller", "Wilson", "Moore"]

start_date = date(2025, 1, 1)
end_date = date(2026, 9, 30)


def random_date():
    days = (end_date - start_date).days
    return (start_date + timedelta(days=random.randint(0, days))).isoformat()

# ----------------create 3 tables: sales, customers, employees------------------
def create_tables(connection):
    connection.executescript("""
        DROP TABLE IF EXISTS sales;
        DROP TABLE IF EXISTS customers;
        DROP TABLE IF EXISTS employees;

        CREATE TABLE sales (
            id INTEGER PRIMARY KEY,
            region TEXT NOT NULL,
            product TEXT NOT NULL,
            revenue REAL NOT NULL,
            date TEXT NOT NULL,
            units_sold INTEGER NOT NULL
        );

        CREATE TABLE customers (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            industry TEXT NOT NULL,
            churn_date TEXT,
            satisfaction_score REAL NOT NULL
        );

        CREATE TABLE employees (
            id INTEGER PRIMARY KEY,
            department TEXT NOT NULL,
            satisfaction_score REAL NOT NULL,
            tenure_years REAL NOT NULL
        );
    """)

#-------------------random imputations------------------
    # sales
def seed_sales(connection):
    rows = [
        (
            i,
            random.choice(regions),
            random.choice(products),
            round(random.uniform(5000, 250000), 2),
            random_date(),
            random.randint(5, 500),
        )
        for i in range(1, 501)
    ]

    connection.executemany("""
        INSERT INTO sales
        (id, region, product, revenue, date, units_sold)
        VALUES (?, ?, ?, ?, ?, ?)
    """, rows)

    # customers
def seed_customers(connection):
    rows = []

    for i in range(1, 501):
        name = f"{random.choice(first_names)} {random.choice(last_names)} {i:03d}"
        churn_date = random_date() if random.random() < 0.35 else None

        rows.append((
            i,
            name,
            random.choice(industries),
            churn_date,
            round(random.uniform(2.0, 5.0), 2),
        ))

    connection.executemany("""
        INSERT INTO customers
        (id, name, industry, churn_date, satisfaction_score)
        VALUES (?, ?, ?, ?, ?)
    """, rows)

    # employees
def seed_employees(connection):
    rows = [
        (
            i,
            random.choice(departments),
            round(random.uniform(2.5, 5.0), 2),
            round(random.uniform(0.5, 20.0), 1),
        )
        for i in range(1, 501)
    ]

    connection.executemany("""
        INSERT INTO employees
        (id, department, satisfaction_score, tenure_years)
        VALUES (?, ?, ?, ?)
    """, rows)

# execution
def main():
    with sqlite3.connect(DB_PATH) as connection:
        create_tables(connection)
        seed_sales(connection)
        seed_customers(connection)
        seed_employees(connection)
        connection.commit()

        for table in ("sales", "customers", "employees"):
            count = connection.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]
            print(f"{table}: {count} rows")

    print(f"Database created at: {DB_PATH.resolve()}")


if __name__ == "__main__":
    main()
