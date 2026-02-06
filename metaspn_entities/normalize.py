from __future__ import annotations

from urllib.parse import urlparse


def normalize_identifier(identifier_type: str, value: str) -> str:
    identifier_type = identifier_type.strip().lower()
    value = value.strip()

    if identifier_type in {"twitter_handle", "github_handle", "handle"}:
        return value.lstrip("@").lower()

    if identifier_type == "email":
        return value.lower()

    if identifier_type == "domain":
        cleaned = value.lower()
        if cleaned.startswith("http://") or cleaned.startswith("https://"):
            cleaned = urlparse(cleaned).netloc or cleaned
        return cleaned.lstrip("www.")

    if identifier_type in {"linkedin_url", "url", "canonical_url"}:
        parsed = urlparse(value)
        if parsed.scheme:
            host = parsed.netloc.lower().lstrip("www.")
            path = parsed.path.rstrip("/")
            return f"{host}{path}".lower()
        return value.lower().rstrip("/")

    if identifier_type == "name":
        return " ".join(value.lower().split())

    return value.lower()


AUTO_MERGE_IDENTIFIER_TYPES = {"email", "canonical_url", "url"}
