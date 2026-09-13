"""Redis flags for crawl queue / schedule pause / cooperative abort."""

from __future__ import annotations

from typing import Any, Optional

CRAWL_QUEUE_KEY = "yojana:crawl_now"
SCHEDULE_PAUSE_KEY = "yojana:crawl_schedule_paused"
ABORT_EXCEPT_KEY = "yojana:crawl_abort_except_run"
ABORT_ALL_KEY = "yojana:crawl_abort_all"


def _client(redis_url: str):
    import redis

    return redis.from_url(redis_url, decode_responses=True)


def pause_schedule(redis_url: str, exclusive_run_id: int | None = None) -> None:
    r = _client(redis_url)
    try:
        r.set(SCHEDULE_PAUSE_KEY, "1")
        if exclusive_run_id is not None:
            r.set(ABORT_EXCEPT_KEY, str(exclusive_run_id))
        r.delete(ABORT_ALL_KEY)
    finally:
        r.close()


def resume_schedule(redis_url: str) -> None:
    r = _client(redis_url)
    try:
        r.delete(SCHEDULE_PAUSE_KEY)
        r.delete(ABORT_EXCEPT_KEY)
        r.delete(ABORT_ALL_KEY)
    finally:
        r.close()


def is_schedule_paused(redis_url: str) -> bool:
    r = _client(redis_url)
    try:
        return r.get(SCHEDULE_PAUSE_KEY) == "1"
    finally:
        r.close()


def request_abort_others(redis_url: str, keep_run_id: int | None = None) -> None:
    """Signal running crawlers to stop unless they are keep_run_id."""
    r = _client(redis_url)
    try:
        if keep_run_id is not None:
            r.set(ABORT_EXCEPT_KEY, str(keep_run_id))
            r.delete(ABORT_ALL_KEY)
        else:
            r.set(ABORT_ALL_KEY, "1")
            r.delete(ABORT_EXCEPT_KEY)
    finally:
        r.close()


def should_abort_run(redis_url: str, run_id: int | None) -> bool:
    if run_id is None:
        return False
    r = _client(redis_url)
    try:
        if r.get(ABORT_ALL_KEY) == "1":
            return True
        keep = r.get(ABORT_EXCEPT_KEY)
        if keep is None:
            return False
        return str(run_id) != str(keep)
    finally:
        r.close()


def clear_queue(redis_url: str) -> int:
    r = _client(redis_url)
    try:
        return int(r.delete(CRAWL_QUEUE_KEY) or 0)
    finally:
        r.close()


def push_crawl_job(redis_url: str, source_id: int, run_id: int) -> None:
    r = _client(redis_url)
    try:
        # Clear old jobs then push exclusive job to front
        r.delete(CRAWL_QUEUE_KEY)
        r.lpush(CRAWL_QUEUE_KEY, f"{source_id}:{run_id}")
    finally:
        r.close()


def clear_exclusive_abort_if_match(redis_url: str, run_id: int | None) -> None:
    if run_id is None:
        return
    r = _client(redis_url)
    try:
        keep = r.get(ABORT_EXCEPT_KEY)
        if keep and str(run_id) == str(keep):
            r.delete(ABORT_EXCEPT_KEY)
    finally:
        r.close()


def control_status(redis_url: str) -> dict[str, Any]:
    r = _client(redis_url)
    try:
        queue_len = int(r.llen(CRAWL_QUEUE_KEY) or 0)
        return {
            "schedule_paused": r.get(SCHEDULE_PAUSE_KEY) == "1",
            "abort_except_run_id": r.get(ABORT_EXCEPT_KEY),
            "abort_all": r.get(ABORT_ALL_KEY) == "1",
            "queue_length": queue_len,
        }
    finally:
        r.close()
