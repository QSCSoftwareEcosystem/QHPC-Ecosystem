"""Minimal hand-rolled S3 (SigV4) client for the databucket/Garage service.

No materials-db or QHPC-specific knowledge lives here — just object PUT/LIST
against one bucket. Follows the project's existing convention of small
stdlib-only clients for separately deployed services (assistant.py,
service_adapters.py) rather than adding a boto3 dependency.
"""

from __future__ import annotations

import hashlib
import hmac
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen


class S3ClientError(RuntimeError):
    """Raised when an S3-compatible request fails or its response is invalid."""


@dataclass(frozen=True)
class ObjectSummary:
    key: str
    size: int
    last_modified: str
    etag: str


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hmac(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()


def _signing_key(
    secret_access_key: str, date_stamp: str, region: str, service: str
) -> bytes:
    k_date = _hmac(f"AWS4{secret_access_key}".encode("utf-8"), date_stamp)
    k_region = _hmac(k_date, region)
    k_service = _hmac(k_region, service)
    return _hmac(k_service, "aws4_request")


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _parse_list_objects(payload: bytes) -> list[ObjectSummary]:
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise S3ClientError(f"invalid ListObjectsV2 response: {exc}") from exc
    objects: list[ObjectSummary] = []
    for element in root:
        if _local_name(element.tag) != "Contents":
            continue
        fields = {_local_name(child.tag): (child.text or "") for child in element}
        objects.append(
            ObjectSummary(
                key=fields.get("Key", ""),
                size=int(fields.get("Size") or "0"),
                last_modified=fields.get("LastModified", ""),
                etag=fields.get("ETag", "").strip('"'),
            )
        )
    return objects


class S3Client:
    """A minimal SigV4-signed client scoped to one S3-compatible bucket."""

    def __init__(
        self,
        *,
        endpoint: str,
        region: str,
        bucket: str,
        access_key_id: str,
        secret_access_key: str,
        timeout_seconds: float = 30.0,
    ) -> None:
        parsed = urlsplit(endpoint)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise S3ClientError("S3 endpoint must be an absolute HTTP(S) URL")
        if not bucket:
            raise S3ClientError("S3 bucket is required")
        self.endpoint = endpoint.rstrip("/")
        self.host = parsed.netloc
        self.region = region
        self.bucket = bucket
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.timeout_seconds = timeout_seconds

    def _signed_request(
        self,
        method: str,
        *,
        key: str = "",
        query: str = "",
        body: bytes = b"",
        content_type: str | None = None,
    ) -> tuple[int, bytes]:
        now = datetime.now(timezone.utc)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")
        object_path = f"{self.bucket}/{key}" if key else self.bucket
        canonical_uri = "/" + quote(object_path, safe="/")
        payload_hash = _sha256_hex(body)

        signed_headers = {
            "host": self.host,
            "x-amz-content-sha256": payload_hash,
            "x-amz-date": amz_date,
        }
        if content_type:
            signed_headers["content-type"] = content_type
        signed_header_names = ";".join(sorted(signed_headers))
        canonical_headers = "".join(
            f"{name}:{signed_headers[name]}\n" for name in sorted(signed_headers)
        )
        canonical_request = "\n".join(
            [
                method,
                canonical_uri,
                query,
                canonical_headers,
                signed_header_names,
                payload_hash,
            ]
        )
        credential_scope = f"{date_stamp}/{self.region}/s3/aws4_request"
        string_to_sign = "\n".join(
            [
                "AWS4-HMAC-SHA256",
                amz_date,
                credential_scope,
                _sha256_hex(canonical_request.encode("utf-8")),
            ]
        )
        signing_key = _signing_key(
            self.secret_access_key, date_stamp, self.region, "s3"
        )
        signature = hmac.new(
            signing_key, string_to_sign.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        authorization = (
            "AWS4-HMAC-SHA256 "
            f"Credential={self.access_key_id}/{credential_scope}, "
            f"SignedHeaders={signed_header_names}, Signature={signature}"
        )
        request_headers = {
            "Host": self.host,
            "X-Amz-Content-Sha256": payload_hash,
            "X-Amz-Date": amz_date,
            "Authorization": authorization,
        }
        if content_type:
            request_headers["Content-Type"] = content_type

        url = f"{self.endpoint}{canonical_uri}"
        if query:
            url += f"?{query}"
        request = Request(url, data=body or None, headers=request_headers, method=method)
        try:
            response = urlopen(request, timeout=self.timeout_seconds)
        except HTTPError as error:
            response = error
        except URLError as error:
            raise S3ClientError(
                f"databucket S3 endpoint is unavailable: {error.reason}"
            ) from error
        try:
            response_body = response.read(10_000_000)
            return response.status, response_body
        finally:
            response.close()

    def put_object(
        self,
        key: str,
        body: bytes,
        *,
        content_type: str = "application/octet-stream",
    ) -> None:
        if not key or key.startswith("/") or ".." in key.split("/"):
            raise S3ClientError(f"invalid object key: {key}")
        status, response_body = self._signed_request(
            "PUT", key=key, body=body, content_type=content_type
        )
        if status >= 300:
            raise S3ClientError(
                f"S3 PUT {key} failed: {status} {response_body[:500]!r}"
            )

    def get_object(self, key: str) -> bytes:
        if not key or key.startswith("/") or ".." in key.split("/"):
            raise S3ClientError(f"invalid object key: {key}")
        status, response_body = self._signed_request("GET", key=key)
        if status >= 300:
            raise S3ClientError(
                f"S3 GET {key} failed: {status} {response_body[:500]!r}"
            )
        return response_body

    def list_objects(self, prefix: str = "") -> list[ObjectSummary]:
        query = "list-type=2"
        if prefix:
            query += f"&prefix={quote(prefix, safe='')}"
        status, response_body = self._signed_request("GET", query=query)
        if status >= 300:
            raise S3ClientError(
                f"S3 LIST {prefix!r} failed: {status} {response_body[:500]!r}"
            )
        return _parse_list_objects(response_body)
