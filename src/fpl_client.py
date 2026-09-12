"""HTTP client for the public FPL API.

Design notes:

- Sequential requests only, spaced by a delay. This is someone else's free
  service and we are a single private league; there is no reason to be greedy.
- Retries with exponential backoff on transient failures (timeouts, 5xx, 429).
- No retry on 404 — a missing endpoint is a finding, not a failure to paper over.
- Never raises on a bad response. Returns a FetchResult so callers can record
  exactly what happened, including the failure. Phase 1 depends on this: a 403
  is as informative as a 200.
- Optionally archives every raw response, so parsing can be redone offline
  without re-requesting anything.
"""

from __future__ import annotations

import gzip
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import requests

from . import config


@dataclass
class FetchResult:
    """The complete outcome of one request, success or failure."""

    url: str
    ok: bool
    status_code: Optional[int] = None
    elapsed_ms: Optional[int] = None
    json_body: Optional[Any] = None
    error: Optional[str] = None
    content_type: Optional[str] = None
    attempts: int = 1
    notes: list[str] = field(default_factory=list)

    @property
    def is_json(self) -> bool:
        return self.json_body is not None

    def summary(self) -> str:
        if self.ok:
            return f"HTTP {self.status_code} in {self.elapsed_ms}ms"
        if self.status_code is not None:
            return f"HTTP {self.status_code} — {self.error or 'failed'}"
        return f"no response — {self.error or 'unknown error'}"


class FPLClient:
    def __init__(
        self,
        base_url: str = config.BASE_URL,
        delay: float = config.REQUEST_DELAY_SECONDS,
        archive_dir: Optional[Path] = None,
        verbose: bool = True,
    ):
        self.base_url = base_url.rstrip("/")
        self.delay = delay
        self.verbose = verbose
        self.archive_dir = archive_dir
        self.request_count = 0
        self._last_request_at = 0.0

        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": config.USER_AGENT,
                "Accept": "application/json",
            }
        )

        if self.archive_dir:
            self.archive_dir.mkdir(parents=True, exist_ok=True)

    # -- internals -----------------------------------------------------------

    def _respect_delay(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)

    def _log(self, message: str) -> None:
        if self.verbose:
            print(message, flush=True)

    def _archive(self, path_key: str, body: Any) -> None:
        if not self.archive_dir:
            return
        safe = path_key.strip("/").replace("/", "__") or "root"
        target = self.archive_dir / f"{safe}.json"
        try:
            target.write_text(json.dumps(body, indent=2)[:50_000_000])
        except (TypeError, ValueError, OSError) as exc:
            self._log(f"    (archive failed for {safe}: {exc})")

    def archive_gzip(self, path_key: str, body: Any) -> Optional[Path]:
        """Compressed archive, for the eventual raw_payloads table."""
        if not self.archive_dir:
            return None
        safe = path_key.strip("/").replace("/", "__") or "root"
        target = self.archive_dir / f"{safe}.json.gz"
        with gzip.open(target, "wt", encoding="utf-8") as fh:
            json.dump(body, fh)
        return target

    # -- public --------------------------------------------------------------

    def get(self, path: str, archive: bool = True) -> FetchResult:
        """GET a path relative to the API base. Never raises."""
        url = f"{self.base_url}/{path.lstrip('/')}"
        last_error = None
        status = None

        for attempt in range(1, config.MAX_RETRIES + 1):
            self._respect_delay()
            started = time.monotonic()
            try:
                resp = self.session.get(
                    url, timeout=config.REQUEST_TIMEOUT_SECONDS
                )
                self._last_request_at = time.monotonic()
                self.request_count += 1
                elapsed_ms = int((time.monotonic() - started) * 1000)
                status = resp.status_code
                ctype = resp.headers.get("Content-Type", "")

                # 404 is a finding. Do not retry it.
                if status == 404:
                    return FetchResult(
                        url=url, ok=False, status_code=404,
                        elapsed_ms=elapsed_ms, content_type=ctype,
                        error="not found", attempts=attempt,
                    )

                # Bot protection / forbidden. Worth reporting immediately.
                if status == 403:
                    return FetchResult(
                        url=url, ok=False, status_code=403,
                        elapsed_ms=elapsed_ms, content_type=ctype,
                        error="forbidden — possible bot protection",
                        attempts=attempt,
                        notes=["A 403 here likely means the request was blocked "
                               "rather than the resource being absent."],
                    )

                if status == 429 or status >= 500:
                    last_error = f"HTTP {status}"
                    if attempt < config.MAX_RETRIES:
                        wait = config.BACKOFF_BASE_SECONDS ** attempt
                        self._log(f"    retry in {wait:.0f}s ({last_error})")
                        time.sleep(wait)
                        continue
                    return FetchResult(
                        url=url, ok=False, status_code=status,
                        elapsed_ms=elapsed_ms, content_type=ctype,
                        error=last_error, attempts=attempt,
                    )

                if status != 200:
                    return FetchResult(
                        url=url, ok=False, status_code=status,
                        elapsed_ms=elapsed_ms, content_type=ctype,
                        error=f"unexpected status {status}", attempts=attempt,
                    )

                try:
                    body = resp.json()
                except ValueError:
                    preview = resp.text[:200].replace("\n", " ")
                    return FetchResult(
                        url=url, ok=False, status_code=status,
                        elapsed_ms=elapsed_ms, content_type=ctype,
                        error="response was not JSON", attempts=attempt,
                        notes=[f"first 200 chars: {preview}"],
                    )

                if archive:
                    self._archive(path, body)

                return FetchResult(
                    url=url, ok=True, status_code=status,
                    elapsed_ms=elapsed_ms, json_body=body,
                    content_type=ctype, attempts=attempt,
                )

            except requests.exceptions.Timeout:
                last_error = "timeout"
            except requests.exceptions.ConnectionError as exc:
                last_error = f"connection error: {exc}"
            except requests.exceptions.RequestException as exc:
                last_error = f"request error: {exc}"

            self._last_request_at = time.monotonic()
            if attempt < config.MAX_RETRIES:
                wait = config.BACKOFF_BASE_SECONDS ** attempt
                self._log(f"    retry in {wait:.0f}s ({last_error})")
                time.sleep(wait)

        return FetchResult(
            url=url, ok=False, status_code=status,
            error=last_error, attempts=config.MAX_RETRIES,
        )
