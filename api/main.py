from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from models.database import get_connection

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/cases")
def get_cases():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT id, case_name, court, date_filed, docket_number FROM cases")
    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    return rows


@app.get("/search")
def search(company: str):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            d.defendant_name,
            d.cleaned_name,
            c.case_name,
            c.court,
            c.date_filed,
            c.docket_number
        FROM defendants d
        JOIN cases c ON d.case_id = c.id
        WHERE d.cleaned_name LIKE %s AND d.is_valid = 1
        """,
        (f"%{company}%",),
    )
    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    if not rows:
        return {"results": [], "count": 0}

    return {"results": rows, "count": len(rows)}
