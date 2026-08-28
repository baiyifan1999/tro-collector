import os

import requests
from dotenv import load_dotenv

from collectors.courtlistener import HEADERS, request_with_retry
from collectors.logger import collector_logger as logger
from models.database import get_connection
from storage.minio_client import upload_file

load_dotenv()

BASE_URL = "https://www.courtlistener.com/api/rest/v4"
PDF_DIR = "/tmp/tro_pdfs"


def fetch_document_list(docket_id):
    url = f"{BASE_URL}/dockets/{docket_id}/"
    response = request_with_retry(url)
    if response is None:
        logger.error(f"Failed to fetch document list for docket {docket_id}")
        return []

    data = response.json()
    raw_docs = data.get("recap_documents", []) or []

    documents = []
    for doc in raw_docs:
        documents.append(
            {
                "doc_id": doc.get("id"),
                "description": doc.get("description", ""),
                "filepath_local": doc.get("filepath_local"),
                "absolute_url": doc.get("absolute_url"),
            }
        )

    return documents


def download_pdf(pdf_url, save_path):
    try:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        response = requests.get(pdf_url, headers=HEADERS, stream=True, timeout=60)
        response.raise_for_status()

        size = 0
        with open(save_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    size += len(chunk)

        logger.info(f"Downloaded {pdf_url} -> {save_path} ({size} bytes)")
        return save_path
    except Exception as e:
        logger.error(f"Failed to download {pdf_url}: {e}")
        return None


def collect_documents(case_id, docket_id):
    documents = fetch_document_list(docket_id)
    uploaded = 0

    conn = get_connection()
    cursor = conn.cursor()

    for doc in documents:
        doc_id = doc["doc_id"]
        description = doc["description"] or ""
        source_url = doc["absolute_url"] or doc["filepath_local"] or ""

        if not source_url:
            logger.error(f"No URL for doc {doc_id} in docket {docket_id}, skipping")
            continue

        doc_type = (
            "schedule_a"
            if any(kw in description.lower() for kw in ("schedule", "exhibit"))
            else "other"
        )

        local_path = os.path.join(PDF_DIR, f"case_{case_id}", f"{doc_id}.pdf")
        saved = download_pdf(source_url, local_path)
        if saved is None:
            continue

        object_name = f"cases/case_{case_id}/{doc_id}.pdf"
        try:
            upload_file(local_path, object_name)
        except Exception as e:
            logger.error(f"Upload failed for doc {doc_id}: {e}")
            continue

        cursor.execute(
            """
            INSERT INTO documents (case_id, doc_type, minio_path, source_url)
            VALUES (%s, %s, %s, %s)
            """,
            (case_id, doc_type, object_name, source_url),
        )
        conn.commit()
        logger.info(f"Saved document record: case_id={case_id} doc_id={doc_id} type={doc_type}")
        uploaded += 1

    cursor.close()
    conn.close()

    logger.info(f"collect_documents: {uploaded}/{len(documents)} docs uploaded for case {case_id}")
    return uploaded
