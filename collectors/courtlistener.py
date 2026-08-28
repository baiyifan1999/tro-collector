import os
import time

import requests
from dotenv import load_dotenv

from collectors.logger import collector_logger as logger

load_dotenv()

COURTLISTENER_TOKEN = os.getenv("COURTLISTENER_TOKEN")

BASE_URL = "https://www.courtlistener.com/api/rest/v4"
SEARCH_URL = f"{BASE_URL}/search/"
PARTIES_URL = f"{BASE_URL}/parties/"

HEADERS = {"Authorization": f"Token {COURTLISTENER_TOKEN}"}

MAX_RETRIES = 3
BASE_BACKOFF_SECONDS = 1


def request_with_retry(url, params=None):
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = requests.get(url, headers=HEADERS, params=params)
        except requests.RequestException as e:
            logger.error(f"Network error requesting {url}: {e}")
            return None

        status = response.status_code

        if status == 429:
            if attempt == MAX_RETRIES:
                logger.error(f"429 rate limit: gave up after {MAX_RETRIES} retries for {url}")
                return None
            retry_after = response.headers.get("Retry-After")
            delay = float(retry_after) if retry_after is not None else 1.0
            logger.warning(
                f"429 rate limited for {url}, waiting {delay:.1f}s "
                f"(attempt {attempt + 1}/{MAX_RETRIES})"
            )
            time.sleep(delay)
            continue

        if status >= 500:
            if attempt == MAX_RETRIES:
                logger.error(f"Server error {status}: gave up after {MAX_RETRIES} retries for {url}")
                return None
            delay = BASE_BACKOFF_SECONDS * (2 ** attempt)  # 1s, 2s, 4s
            logger.warning(
                f"Server error {status} for {url}, retrying in {delay:.1f}s "
                f"(attempt {attempt + 1}/{MAX_RETRIES})"
            )
            time.sleep(delay)
            continue

        if status >= 400:
            logger.error(f"Client error {status} for {url}, not retrying")
            return None

        return response

    return None


def search_tro_cases():
    params = {
        "q": "trademark infringement temporary restraining order",
        "type": "r",
        "court": "ilnd cacd nysd",
        "filed_after": "2020-01-01",
    }

    response = request_with_retry(SEARCH_URL, params=params)
    if response is None:
        logger.error("Failed to search TRO cases, returning empty list")
        return []

    data = response.json()
    results = data.get("results", [])

    cases = []
    for result in results:
        cases.append(
            {
                "id": result.get("docket_id"),
                "case_name": result.get("caseName"),
                "court": result.get("court"),
                "date_filed": result.get("dateFiled"),
                "docket_number": result.get("docketNumber"),
            }
        )

    return cases


def fetch_parties(docket_id):
    response = request_with_retry(PARTIES_URL, params={"docket": docket_id})
    if response is None:
        logger.error(f"Failed to fetch parties for docket {docket_id}")
        return []

    data = response.json()
    results = data.get("results", [])

    defendants = []
    for party in results:
        party_types = party.get("party_types") or []
        is_defendant = any(
            (pt.get("name") or "").lower() == "defendant" for pt in party_types
        )
        if is_defendant:
            name = party.get("name")
            if name:
                defendants.append(name)

    return defendants


def collect_all():
    cases = search_tro_cases()
    collected = []

    for case in cases:
        case_name = case.get("case_name")
        docket_id = case.get("id")

        logger.info(f"Processing case: {case_name} (docket id: {docket_id})")

        try:
            defendants = fetch_parties(docket_id)
        except Exception as e:
            logger.error(f"Error processing case {case_name}: {e}")
            continue

        collected.append(
            {
                "case_name": case_name,
                "court": case.get("court"),
                "date_filed": case.get("date_filed"),
                "docket_number": case.get("docket_number"),
                "docket_id": docket_id,
                "defendants": defendants,
            }
        )

        time.sleep(1)

    return collected
