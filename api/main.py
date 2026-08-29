import time
from collections import defaultdict
from typing import Optional

from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": "输入参数格式不正确"},
    )


class RateLimiter:
    def __init__(self, max_requests: int = 60, window: int = 60):
        self.max_requests = max_requests
        self.window = window
        self._timestamps: dict[str, list[float]] = defaultdict(list)

    def check(self, ip: str) -> None:
        now = time.monotonic()
        cutoff = now - self.window
        ts = self._timestamps[ip]
        # drop timestamps outside the window
        self._timestamps[ip] = [t for t in ts if t > cutoff]
        if len(self._timestamps[ip]) >= self.max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="请求过于频繁，请稍后再试",
            )
        self._timestamps[ip].append(now)


rate_limiter = RateLimiter()

_bearer = HTTPBearer()


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(_bearer)) -> str:
    return verify_token(credentials.credentials)


def check_rate_limit(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    rate_limiter.check(ip)


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
            doc.source_url,
            rs.risk_score
        FROM defendants d
        JOIN cases c ON d.case_id = c.id
        LEFT JOIN documents doc ON doc.id = d.source_doc_id
        LEFT JOIN risk_scores rs ON rs.company_name = d.cleaned_name
        WHERE d.cleaned_name LIKE %s AND d.is_valid = 1
        ORDER BY c.date_filed DESC
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
def get_cases(
    # current_user: str = Depends(get_current_user),  # TODO: re-enable in production
    _: None = Depends(check_rate_limit),
):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, case_name, court, date_filed, docket_number FROM cases")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


@app.get("/search")
def search(
    company: str = Query(min_length=1, max_length=100),
    platform: Optional[str] = Query(default=None, max_length=50),
    court: Optional[str] = Query(default=None, max_length=100),
    after_date: Optional[str] = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    min_score: Optional[int] = Query(default=None, ge=0, le=100),
    # current_user: str = Depends(get_current_user),  # TODO: re-enable in production
    _: None = Depends(check_rate_limit),
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
