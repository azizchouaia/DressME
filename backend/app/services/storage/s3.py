from typing import Any

from app.services.storage.base import StorageService


class S3Storage(StorageService):
    """S3-compatible storage: AWS S3, Cloudflare R2, Supabase Storage, MinIO.

    Requires `boto3` (see requirements.txt). R2 and Supabase work by pointing
    `endpoint_url` at the provider's S3 endpoint.
    """

    def __init__(
        self,
        *,
        bucket: str,
        endpoint_url: str | None,
        access_key: str | None,
        secret_key: str | None,
        region: str,
        public_base_url: str,
    ) -> None:
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError("Install boto3 to use STORAGE_BACKEND=s3") from exc

        self.bucket = bucket
        self.public_base_url = public_base_url.rstrip("/")
        self._client: Any = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
        )

    def save(self, key: str, data: bytes, content_type: str) -> str:
        self._client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)
        return self.url_for(key)

    def read(self, key: str) -> bytes:
        response = self._client.get_object(Bucket=self.bucket, Key=key)
        body: bytes = response["Body"].read()
        return body

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self.bucket, Key=key)

    def url_for(self, key: str) -> str:
        return f"{self.public_base_url}/{key}"
