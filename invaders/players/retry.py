"""Retry model calls through network outages.

In turn mode the game waits for every decision, so a dropped connection must cost time,
never a decision. A transient failure (no connection, timeout, rate limit, server error)
is retried with backoff until the connection returns or MAX_OUTAGE_S has passed. Only
then, or on a permanent failure (a bad request, a refused key), does the caller fall back
to holding the previous action.
"""

import time

import httpx

TRANSIENT_STATUSES = {408, 409, 425, 429, 500, 502, 503, 504, 529}
MAX_OUTAGE_S = 600.0
FIRST_DELAY_S = 0.5
MAX_DELAY_S = 30.0


class TransientStatus(Exception):
    """An HTTP response whose status says: try again."""

    def __init__(self, status: int) -> None:
        super().__init__(f"HTTP {status}")
        self.status = status


def status_of(error: Exception) -> int | None:
    """The HTTP status an error carries, or None for a connection-level error."""
    return getattr(error, "status", None) or getattr(error, "status_code", None)


def is_transient(error: Exception) -> bool:
    status = status_of(error)
    if status is not None:
        return status in TRANSIENT_STATUSES
    if isinstance(error, (httpx.TransportError, ConnectionError, TimeoutError, OSError)):
        return True
    # The SDKs wrap connection failures in their own classes (for example
    # TypeSafeAPIConnectionError, anthropic.APIConnectionError, APITimeoutError).
    return any(word in type(error).__name__ for word in ("Connect", "Timeout"))


def call_with_retry(call, on_retry=None, max_outage_s: float = MAX_OUTAGE_S, sleep=time.sleep):
    """Return (call(), retries), retrying transient failures with backoff.

    on_retry(error) runs before each retry, for example to rebuild a client whose
    connection broke. The last error is raised when the failure is permanent or the
    outage lasts longer than max_outage_s.
    """
    delay, waited, retries = FIRST_DELAY_S, 0.0, 0
    while True:
        try:
            return call(), retries
        except Exception as error:  # noqa: BLE001 - classified below
            if not is_transient(error) or waited >= max_outage_s:
                raise
            if on_retry is not None:
                on_retry(error)
            sleep(delay)
            waited += delay
            retries += 1
            delay = min(delay * 2, MAX_DELAY_S)
