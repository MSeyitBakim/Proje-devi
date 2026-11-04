from datetime import timedelta

import pytest

from app.core.exceptions import InvalidStateError
from app.repositories.crawl import CrawlJobRepository, CrawlQueue
from app.services.bloom import SeenUrlFilter
from tests.conftest import NOW


def queue_for(conn, **kwargs) -> CrawlQueue:
    return CrawlQueue(conn, max_attempts=3, retry_base_s=10, lease_s=60, **kwargs)


def test_enqueue_deduplicates_and_claim_is_exclusive(conn) -> None:
    queue = queue_for(conn)
    assert queue.enqueue_url("https://a.com/1", NOW)
    assert not queue.enqueue_url("https://a.com/1", NOW)
    assert queue.check_visited("https://a.com/1") and not queue.check_visited("https://a.com/2")
    first = queue.claim_next_url(NOW)
    assert first["url"] == "https://a.com/1" and first["status"] == "in_progress"
    assert queue.claim_next_url(NOW) is None  # nothing else, and the claimed row is not re-issued


def test_claim_order_and_stale_lease_reclaim(conn) -> None:
    queue = queue_for(conn)
    queue.enqueue_url("https://a.com/1", NOW)
    queue.enqueue_url("https://a.com/2", NOW + timedelta(seconds=1))
    claimed = queue.claim_next_url(NOW + timedelta(seconds=2))
    assert claimed["url"] == "https://a.com/1"
    nxt = queue.claim_next_url(NOW + timedelta(seconds=2))
    assert nxt["url"] == "https://a.com/2"
    # the first worker "crashed": after the lease expires the row becomes claimable again
    reclaimed = queue.claim_next_url(NOW + timedelta(seconds=120))
    assert reclaimed["url"] == "https://a.com/1"


def test_retry_with_backoff_then_permanent_failure(conn) -> None:
    queue = queue_for(conn)
    queue.enqueue_url("https://a.com/1", NOW)
    item = queue.claim_next_url(NOW)
    assert queue.mark_failed(item["id"], "timeout", NOW, retry=True) == "pending"
    assert queue.claim_next_url(NOW + timedelta(seconds=5)) is None  # backoff: 10s
    assert [r["url"] for r in queue.get_retryable_urls(NOW + timedelta(seconds=11))] == ["https://a.com/1"]
    item = queue.claim_next_url(NOW + timedelta(seconds=11))
    t2 = NOW + timedelta(seconds=11)
    assert queue.mark_failed(item["id"], "timeout", t2, retry=True) == "pending"
    assert queue.claim_next_url(t2 + timedelta(seconds=15)) is None  # 20s second delay
    item = queue.claim_next_url(t2 + timedelta(seconds=21))
    assert queue.mark_failed(item["id"], "timeout", t2, retry=True) == "failed"  # attempts exhausted


def test_non_retryable_failure_and_success(conn) -> None:
    queue = queue_for(conn)
    queue.enqueue_url("https://a.com/1", NOW)
    queue.enqueue_url("https://a.com/2", NOW)
    one, two = queue.claim_next_url(NOW), queue.claim_next_url(NOW)
    assert queue.mark_failed(one["id"], "http_404", NOW, retry=False, status_code=404) == "failed"
    queue.mark_crawled(two["id"], 200, NOW)
    assert queue.status_counts() == {"pending": 0, "in_progress": 0, "done": 1, "failed": 1}


def test_force_requeue_resets_finished_url_but_not_active_one(conn) -> None:
    queue = queue_for(conn)
    queue.enqueue_url("https://a.com/1", NOW)
    item = queue.claim_next_url(NOW)
    assert not queue.enqueue_url("https://a.com/1", NOW, force=True)  # in progress
    queue.mark_crawled(item["id"], 200, NOW)
    assert queue.enqueue_url("https://a.com/1", NOW, force=True)
    assert queue.claim_next_url(NOW)["attempts"] == 0


def test_bloom_gate_never_hides_known_urls_even_when_stale(conn) -> None:
    gate = SeenUrlFilter(capacity=100, error_rate=0.01, enabled=True)
    queue = queue_for(conn, seen=gate)
    queue.enqueue_url("https://a.com/known", NOW)
    # a second process inserts a URL our filter has never seen
    conn.execute(
        "INSERT INTO crawl_urls (url, next_attempt_at, created_at, updated_at) VALUES (?, 'x','x','x')",
        ("https://a.com/other-process",),
    )
    assert queue.check_visited("https://a.com/known")
    # A stale filter may report "not visited" for rows another process inserted. That is safe:
    # the authoritative UNIQUE constraint still rejects the duplicate insert.
    assert not queue.enqueue_url("https://a.com/other-process", NOW)
    assert queue.count_for_job(0) == 0
    assert conn.execute("SELECT COUNT(*) FROM crawl_urls").fetchone()[0] == 2
    queue.rebuild_seen_filter()
    assert queue.check_visited("https://a.com/other-process")
    assert queue.filter_unseen(["https://a.com/known", "https://a.com/new"]) == ["https://a.com/new"]


def test_job_state_machine(conn) -> None:
    jobs = CrawlJobRepository(conn)
    job_id = jobs.create("https://a.com/", 5, 1, NOW)
    with pytest.raises(InvalidStateError):
        jobs.transition(job_id, "completed", NOW)
    jobs.transition(job_id, "running", NOW)
    jobs.transition(job_id, "completed", NOW)
    with pytest.raises(InvalidStateError):
        jobs.transition(job_id, "running", NOW)
    with pytest.raises(InvalidStateError):
        jobs.transition(999, "running", NOW)
