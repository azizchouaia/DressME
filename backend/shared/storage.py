"""S3 / MinIO helper shared by all agents."""

import boto3

from shared.config import settings


def s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
    )


def upload_bytes(key: str, data: bytes, content_type: str = "image/png") -> str:
    s3_client().put_object(Bucket=settings.s3_bucket, Key=key, Body=data, ContentType=content_type)
    return f"s3://{settings.s3_bucket}/{key}"
