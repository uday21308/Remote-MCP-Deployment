from fastmcp import FastMCP
import os
import sqlite3
import tempfile

# Use OS temp directory to ensure write access
BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, "expenses.db")
CATEGORIES_PATH = os.path.join(BASE_DIR, "categories.json")

print(f"Database path: {DB_PATH}")

# MCP server object (required by FastMCP CLI)
mcp = FastMCP("ExpenseTracker")
server = mcp   # <-- IMPORTANT: FastMCP looks for this variable


# -------------------------------
# Initialize DB (SYNC SAFE)
# -------------------------------
def init_db():
    try:
        import sqlite3
        with sqlite3.connect(DB_PATH) as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("""
                CREATE TABLE IF NOT EXISTS expenses(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    amount REAL NOT NULL,
                    category TEXT NOT NULL,
                    subcategory TEXT DEFAULT '',
                    note TEXT DEFAULT ''
                )
            """)
            c.execute("INSERT OR IGNORE INTO expenses(date, amount, category) VALUES ('2000-01-01', 0, 'test')")
            c.execute("DELETE FROM expenses WHERE category = 'test'")
            print("Database initialized successfully.")
    except Exception as e:
        print(f"DB init error: {e}")
        raise


init_db()


# -------------------------------
# TOOLS
# -------------------------------

@mcp.tool()
async def add_expense(date, amount, category, subcategory="", note=""):
    """Add a new expense entry."""
    try:
        async with sqlite3.connect(DB_PATH) as c:
            cur = await c.execute(
                "INSERT INTO expenses(date, amount, category, subcategory, note) VALUES (?,?,?,?,?)",
                (date, amount, category, subcategory, note)
            )
            await c.commit()
            return {
                "status": "success",
                "id": cur.lastrowid,
                "message": "Expense added successfully"
            }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
async def list_expenses(start_date, end_date):
    """List expenses in a date range."""
    try:
        async with sqlite3.connect(DB_PATH) as c:
            cur = await c.execute(
                """
                SELECT id, date, amount, category, subcategory, note
                FROM expenses
                WHERE date BETWEEN ? AND ?
                ORDER BY date DESC, id DESC
                """,
                (start_date, end_date)
            )
            rows = await cur.fetchall()
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in rows]
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
async def summarize(start_date, end_date, category=None):
    """Summarize expenses by category."""
    try:
        async with sqlite3.connect(DB_PATH) as c:
            query = """
                SELECT category, SUM(amount) AS total_amount, COUNT(*) as count
                FROM expenses
                WHERE date BETWEEN ? AND ?
            """
            params = [start_date, end_date]

            if category:
                query += " AND category = ?"
                params.append(category)

            query += " GROUP BY category ORDER BY total_amount DESC"

            cur = await c.execute(query, params)
            rows = await cur.fetchall()
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in rows]
    except Exception as e:
        return {"status": "error", "message": str(e)}


# -------------------------------
# RESOURCE
# -------------------------------
@mcp.resource("expense:///categories", mime_type="application/json")
def categories():
    try:
        if os.path.exists(CATEGORIES_PATH):
            return open(CATEGORIES_PATH, "r", encoding="utf-8").read()

        import json
        default_categories = {
            "categories": [
                "Food & Dining", "Transportation", "Shopping",
                "Entertainment", "Bills & Utilities", "Healthcare",
                "Travel", "Education", "Business", "Other"
            ]
        }
        return json.dumps(default_categories, indent=2)

    except Exception as e:
        return f'{{"error": "{str(e)}"}}'


# -------------------------------
# MAIN (HTTP Server)
# -------------------------------
if __name__ == "__main__":
    mcp.run(
        transport="http",
        host="0.0.0.0",
        port=8000
    )
