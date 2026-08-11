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

MAX_RETRIES = 4
BASE_BACKOFF_SECONDS = 1
MAX_BACKOFF_SECONDS = 10


def request_with_retry(url, params=None):
    for attempt in range(MAX_RETRIES + 1):
        response = requests.get(url, headers=HEADERS, params=params)

        if response.status_code == 429 or response.status_code >= 500:
            if attempt == MAX_RETRIES:
                response.raise_for_status()

            retry_after = response.headers.get("Retry-After")
            if retry_after is not None:
                delay = float(retry_after)
            else:
                delay = min(
                    BASE_BACKOFF_SECONDS * (2 ** attempt), MAX_BACKOFF_SECONDS
                )

            logger.warning(
                f"Got {response.status_code} for {url}, "
                f"retrying in {delay:.1f}s (attempt {attempt + 1}/{MAX_RETRIES})"
            )
            time.sleep(delay)
            continue

        response.raise_for_status()
        return response

    return response


def search_tro_cases():
    params = {
        "q": "trademark infringement temporary restraining order",
        "type": "r",
        "court": "ilnd cacd nysd",
        "filed_after": "2020-01-01",
    }

    try:
        response = request_with_retry(SEARCH_URL, params=params)
    except requests.RequestException as e:
        logger.error(f"Error searching TRO cases: {e}")
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
    try:
        response = request_with_retry(PARTIES_URL, params={"docket": docket_id})
    except requests.RequestException as e:
        logger.error(f"Error fetching parties for docket {docket_id}: {e}")
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
                "defendants": defendants,
            }
        )

        time.sleep(1)

    return collected
