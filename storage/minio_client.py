import os
from datetime import timedelta

from dotenv import load_dotenv
from minio import Minio
from minio.error import S3Error

from collectors.logger import collector_logger as logger

load_dotenv()

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "tro-documents")


def get_client() -> Minio:
    return Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=False,
    )


def ensure_bucket():
    client = get_client()
    if not client.bucket_exists(MINIO_BUCKET):
        client.make_bucket(MINIO_BUCKET)
        logger.info(f"Created bucket: {MINIO_BUCKET}")
    else:
        logger.info(f"Bucket already exists: {MINIO_BUCKET}")


def upload_file(local_path: str, object_name: str) -> str:
    client = get_client()
    try:
        client.fput_object(MINIO_BUCKET, object_name, local_path)
        logger.info(f"Uploaded {local_path} -> {MINIO_BUCKET}/{object_name}")
        return object_name
    except S3Error as e:
        logger.error(f"Failed to upload {local_path}: {e}")
        raise


def get_presigned_url(object_name: str, expires_hours: int = 1) -> str:
    client = get_client()
    url = client.presigned_get_object(
        MINIO_BUCKET,
        object_name,
        expires=timedelta(hours=expires_hours),
    )
    return url
