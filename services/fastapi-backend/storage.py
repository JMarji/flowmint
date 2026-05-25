import os
import uuid
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
import logging

logger = logging.getLogger(__name__)
_s3 = None


def _get_s3():
    global _s3
    if _s3 is None:
        raw_endpoint = os.environ["LINODE_OBJ_ENDPOINT"]
        bucket = os.environ["LINODE_OBJ_BUCKET"]
        # Strip bucket prefix if present (e.g. "flowmint.us-southeast-1..." → "us-southeast-1...")
        if raw_endpoint.startswith(f"{bucket}."):
            raw_endpoint = raw_endpoint[len(bucket) + 1:]
        endpoint_url = raw_endpoint if raw_endpoint.startswith("https://") else f"https://{raw_endpoint}"
        _s3 = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=os.environ["LINODE_OBJ_ACCESS_KEY"],
            aws_secret_access_key=os.environ["LINODE_OBJ_SECRET_KEY"],
            config=Config(signature_version="s3v4"),
        )
    return _s3


def make_s3_key(user_id: int, filename: str) -> str:
    safe_name = filename.replace(" ", "_")
    return f"user_{user_id}/{uuid.uuid4().hex}/{safe_name}"


def presigned_upload_url(s3_key: str, content_type: str, expires: int = 3600) -> str:
    bucket = os.environ["LINODE_OBJ_BUCKET"]
    return _get_s3().generate_presigned_url(
        "put_object",
        Params={"Bucket": bucket, "Key": s3_key, "ContentType": content_type},
        ExpiresIn=expires,
    )


def presigned_download_url(s3_key: str, filename: str, expires: int = 900) -> str:
    bucket = os.environ["LINODE_OBJ_BUCKET"]
    return _get_s3().generate_presigned_url(
        "get_object",
        Params={
            "Bucket": bucket,
            "Key": s3_key,
            "ResponseContentDisposition": f'attachment; filename="{filename}"',
        },
        ExpiresIn=expires,
    )


def delete_object(s3_key: str):
    bucket = os.environ["LINODE_OBJ_BUCKET"]
    try:
        _get_s3().delete_object(Bucket=bucket, Key=s3_key)
    except ClientError as e:
        logger.error("S3 delete failed for key %s: %s", s3_key, e)
