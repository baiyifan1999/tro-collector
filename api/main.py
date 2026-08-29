from typing import Optional

from fastapi import Depends, FastAPI, Form, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from auth.jwt_handler import create_token, verify_token
from auth.users import get_user_hash, verify_password
from collectors.logger import collector_logger as logger
from models.database import get_connection
from search.es_client import get_client

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

_bearer = HTTPBearer()


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(_bearer)) -> str:
    return verify_token(credentials.credentials)


def search_es(
    name: Optional[str],
    platform: Optional[str],
    court: Optional[str],
    after_date: Optional[str],
    min_score: Optional[int],
) -> list:
    must = []
    if name:
        must.append({"match": {"store_name": {"query": name, "fuzziness": "AUTO"}}})

    filters = []
    if platform:
        filters.append({"term": {"platform": platform}})
    if court:
        filters.append({"term": {"court": court}})
    if after_date:
        filters.append({"range": {"date_filed": {"gte": after_date}}})
    if min_score is not None:
        filters.append({"range": {"risk_score": {"gte": min_score}}})

    query = {"bool": {"must": must, "filter": filters}}

    client = get_client()
    resp = client.search(
        index="tro_defendants",
        query=query,
        sort=[{"date_filed": {"order": "desc"}}],
        size=100,
    )
    return [hit["_source"] for hit in resp["hits"]["hits"]]


def _search_mysql(company: str) -> list:
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT
            d.defendant_name,
            d.cleaned_name  AS store_name,
            d.platform,
            c.case_name,
            c.court,
            c.date_filed,
            c.docket_number,
            doc.source_url
        FROM defendants d
        JOIN cases c ON d.case_id = c.id
        LEFT JOIN documents doc ON doc.id = d.source_doc_id
        WHERE d.cleaned_name LIKE %s AND d.is_valid = 1
        """,
        (f"%{company}%",),
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


@app.post("/login")
def login(username: str = Form(...), password: str = Form(...)):
    hashed = get_user_hash(username)
    if not hashed or not verify_password(password, hashed):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )
    token = create_token(username)
    return {"access_token": token, "token_type": "bearer"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/cases")
def get_cases(current_user: str = Depends(get_current_user)):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, case_name, court, date_filed, docket_number FROM cases")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


@app.get("/search")
def search(
    company: str,
    platform: Optional[str] = None,
    court: Optional[str] = None,
    after_date: Optional[str] = None,
    min_score: Optional[int] = None,
    current_user: str = Depends(get_current_user),
):
    # Try ES first
    try:
        results = search_es(
            name=company,
            platform=platform,
            court=court,
            after_date=after_date,
            min_score=min_score,
        )
        if results:
            logger.info(f"search '{company}': ES returned {len(results)} hits")
            return {"results": results, "count": len(results), "source": "es"}
        logger.info(f"search '{company}': ES returned 0 hits, falling back to MySQL")
    except Exception as e:
        logger.error(f"search '{company}': ES error ({e}), falling back to MySQL")

    # Fallback: MySQL
    rows = _search_mysql(company)
    logger.info(f"search '{company}': MySQL returned {len(rows)} rows")
    if not rows:
        return {"results": [], "count": 0, "source": "mysql"}
    return {"results": rows, "count": len(rows), "source": "mysql"}
