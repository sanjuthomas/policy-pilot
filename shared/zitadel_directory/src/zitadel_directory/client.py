from __future__ import annotations

import base64
import json
import logging
from typing import Any
from urllib.parse import urlparse

import httpx

from zitadel_directory.models import DirectoryUser

logger = logging.getLogger(__name__)

_PAGE_SIZE = 100


class ZitadelDirectoryError(RuntimeError):
    """Raised when ZITADEL directory listing fails."""


def _parse_json_list(raw: str) -> list[str]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = [part.strip() for part in raw.split(",") if part.strip()]
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed]


def _decode_metadata_values(raw: dict[str, Any]) -> dict[str, str]:
    decoded: dict[str, str] = {}
    for key, value in raw.items():
        if not isinstance(value, str):
            continue
        try:
            decoded[key] = base64.b64decode(value).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            decoded[key] = value
    return decoded


def build_directory_client(
    *,
    base_url: str,
    pat: str,
    host_header: str | None = None,
    org_id: str | None = None,
    timeout: float = 30.0,
    attach_org: bool = True,
) -> ZitadelDirectoryClient:
    """Construct a directory client; optionally attach ``x-zitadel-orgid``.

    When ``attach_org`` is true and org resolution fails, falls back to the
    unscoped client (org header is optional for some deployments).
    """
    client = ZitadelDirectoryClient(
        base_url=base_url,
        pat=pat,
        host_header=host_header,
        org_id=org_id,
        timeout=timeout,
    )
    if not attach_org or org_id:
        return client
    try:
        return client.with_org()
    except Exception:
        logger.warning("directory client continuing without org header", exc_info=True)
        return client


class ZitadelDirectoryClient:
    """List human users and hydrate custom metadata for directory queries."""

    def __init__(
        self,
        *,
        base_url: str,
        pat: str,
        host_header: str | None = None,
        org_id: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        if not base_url.strip():
            raise ZitadelDirectoryError("ZITADEL base_url is required")
        if not pat.strip():
            raise ZitadelDirectoryError("ZITADEL service PAT is required")
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._headers: dict[str, str] = {
            "Authorization": f"Bearer {pat}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        host = (host_header or "").strip()
        if not host:
            host = urlparse(self._base_url).netloc
        if host and "://" not in host:
            self._headers["Host"] = host
        if org_id:
            self._headers["x-zitadel-orgid"] = org_id

    def resolve_org_id(self) -> str:
        payload = self._request("GET", "/management/v1/orgs/me")
        org_id = ((payload.get("org") or {}).get("id") or "").strip()
        if not org_id:
            raise ZitadelDirectoryError("could not resolve organization id")
        return org_id

    def with_org(self, org_id: str | None = None) -> ZitadelDirectoryClient:
        """Return a client that includes ``x-zitadel-orgid`` (resolved if omitted)."""
        resolved = org_id or self.resolve_org_id()
        return ZitadelDirectoryClient(
            base_url=self._base_url,
            pat=self._headers["Authorization"].removeprefix("Bearer ").strip(),
            host_header=self._headers.get("Host"),
            org_id=resolved,
            timeout=self._timeout,
        )

    def list_directory_users(self) -> list[DirectoryUser]:
        """Return human users that carry ``subject_user_id`` (or username) metadata."""
        entries = self._list_user_entries()
        users: list[DirectoryUser] = []
        for entry in entries:
            if entry.get("human") is None and entry.get("machine") is not None:
                continue
            zitadel_user_id = str(entry.get("userId") or entry.get("user_id") or "").strip()
            if not zitadel_user_id:
                continue
            username = str(entry.get("username") or "").strip()
            if username.startswith("svc-"):
                continue
            try:
                metadata = self._fetch_metadata(zitadel_user_id)
            except ZitadelDirectoryError:
                logger.warning("skipping user %s — metadata fetch failed", zitadel_user_id)
                continue
            user = self._to_directory_user(entry, metadata, zitadel_user_id=zitadel_user_id)
            if user is None:
                continue
            if user.user_id.startswith("svc-"):
                continue
            users.append(user)
        users.sort(key=lambda row: row.user_id)
        return users

    def _list_user_entries(self) -> list[dict[str, Any]]:
        offset = 0
        results: list[dict[str, Any]] = []
        while True:
            payload = self._request(
                "POST",
                "/v2/users",
                json_body={
                    "query": {"offset": offset, "limit": _PAGE_SIZE, "asc": True},
                    "sortingColumn": "USER_FIELD_NAME_USER_NAME",
                },
            )
            page = payload.get("result") or []
            if not isinstance(page, list):
                break
            results.extend(entry for entry in page if isinstance(entry, dict))
            if len(page) < _PAGE_SIZE:
                break
            offset += _PAGE_SIZE
            if offset > 10_000:
                logger.warning("directory list stopped after 10_000 users")
                break
        return results

    def _fetch_metadata(self, zitadel_user_id: str) -> dict[str, str]:
        payload = self._request(
            "POST",
            f"/v2/users/{zitadel_user_id}/metadata/search",
            json_body={},
        )
        metadata: dict[str, str] = {}
        for entry in payload.get("metadata") or []:
            if not isinstance(entry, dict):
                continue
            key = entry.get("key")
            value = entry.get("value")
            if isinstance(key, str) and isinstance(value, str):
                metadata[key] = value
        return _decode_metadata_values(metadata)

    def _to_directory_user(
        self,
        entry: dict[str, Any],
        metadata: dict[str, str],
        *,
        zitadel_user_id: str,
    ) -> DirectoryUser | None:
        username = str(entry.get("username") or "").strip()
        human = entry.get("human") if isinstance(entry.get("human"), dict) else {}
        profile = human.get("profile") if isinstance(human.get("profile"), dict) else {}

        user_id = (
            metadata.get("subject_user_id")
            or username
            or str(entry.get("preferredLoginName") or "").split("@", 1)[0]
        ).strip()
        if not user_id:
            return None

        given_name = (
            metadata.get("given_name")
            or str(profile.get("givenName") or "").strip()
            or user_id
        )
        family_name = (
            metadata.get("family_name")
            or str(profile.get("familyName") or "").strip()
            or user_id
        )
        title = (metadata.get("title") or "").strip()
        roles_raw = metadata.get("roles")
        roles = _parse_json_list(roles_raw) if roles_raw else []
        if not title or not roles:
            # Incomplete seed metadata — not usable for OPA / directory answers.
            return None

        groups_raw = metadata.get("groups")
        groups = _parse_json_list(groups_raw) if groups_raw else []
        covering_raw = metadata.get("covering_lobs")
        covering_lobs = _parse_json_list(covering_raw) if covering_raw else []

        return DirectoryUser(
            user_id=user_id,
            given_name=given_name,
            family_name=family_name,
            title=title,
            roles=roles,
            groups=groups,
            lob=(metadata.get("lob") or None),
            supervisor_id=(metadata.get("supervisor_id") or None),
            covering_lobs=covering_lobs,
            zitadel_user_id=zitadel_user_id,
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with httpx.Client(timeout=self._timeout) as client:
            response = client.request(
                method,
                f"{self._base_url}{path}",
                headers=self._headers,
                json=json_body,
            )
        if response.status_code >= 400:
            detail = response.text.strip() or response.reason_phrase
            raise ZitadelDirectoryError(
                f"{method} {path} failed ({response.status_code}): {detail}"
            )
        if not response.content:
            return {}
        payload = response.json()
        if not isinstance(payload, dict):
            raise ZitadelDirectoryError(f"{method} {path} returned non-object JSON")
        return payload
