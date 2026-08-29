import os

from dotenv import load_dotenv
from elasticsearch import Elasticsearch, NotFoundError
from elasticsearch import helpers

from collectors.logger import collector_logger as logger

load_dotenv()

ES_HOST = os.getenv("ES_HOST", "localhost")
ES_PORT = os.getenv("ES_PORT", "9200")

INDEX_NAME = "tro_defendants"

INDEX_MAPPING = {
    "properties": {
        "store_name":    {"type": "text",    "analyzer": "standard"},
        "platform":      {"type": "keyword"},
        "court":         {"type": "keyword"},
        "date_filed":    {"type": "date"},
        "case_name":     {"type": "text"},
        "case_id":       {"type": "integer"},
        "defendant_id":  {"type": "integer"},
        "source_url":    {"type": "keyword"},
        "risk_score":    {"type": "integer"},
    }
}


def get_client() -> Elasticsearch:
    return Elasticsearch(f"http://{ES_HOST}:{ES_PORT}")


def ensure_index():
    client = get_client()
    if client.indices.exists(index=INDEX_NAME):
        logger.info(f"ES index '{INDEX_NAME}' already exists, skipping creation")
        return

    client.indices.create(index=INDEX_NAME, mappings=INDEX_MAPPING)
    logger.info(f"ES index '{INDEX_NAME}' created")


def index_defendant(doc: dict):
    client = get_client()
    try:
        client.index(
            index=INDEX_NAME,
            id=doc["defendant_id"],
            document=doc,
        )
        logger.info(f"Indexed defendant {doc['defendant_id']} ({doc.get('store_name')})")
    except Exception as e:
        logger.error(f"Failed to index defendant {doc.get('defendant_id')}: {e}")


def bulk_index_defendants(docs: list) -> int:
    if not docs:
        return 0

    client = get_client()
    actions = [
        {
            "_index": INDEX_NAME,
            "_id": doc["defendant_id"],
            **doc,
        }
        for doc in docs
    ]

    try:
        success, errors = helpers.bulk(client, actions, raise_on_error=False)
        if errors:
            for err in errors:
                logger.error(f"Bulk index error: {err}")
        logger.info(f"Bulk indexed {success}/{len(docs)} defendants")
        return success
    except Exception as e:
        logger.error(f"Bulk index failed: {e}")
        return 0
