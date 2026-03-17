"""Tests for TokenBucketRateLimiter."""

import threading
import time

from api.rate_limiter import TokenBucketRateLimiter


class TestTokenBucketRateLimiter:
    def test_allows_within_limit(self):
        limiter = TokenBucketRateLimiter(requests_per_window=5, window_seconds=60)
        for _ in range(5):
            assert limiter.is_allowed("client1") is True

    def test_denies_after_exhaustion(self):
        limiter = TokenBucketRateLimiter(requests_per_window=3, window_seconds=60)
        for _ in range(3):
            limiter.is_allowed("client1")
        assert limiter.is_allowed("client1") is False

    def test_separate_clients(self):
        limiter = TokenBucketRateLimiter(requests_per_window=2, window_seconds=60)
        limiter.is_allowed("client1")
        limiter.is_allowed("client1")
        assert limiter.is_allowed("client1") is False
        assert limiter.is_allowed("client2") is True

    def test_token_refill(self):
        limiter = TokenBucketRateLimiter(requests_per_window=1, window_seconds=1)
        assert limiter.is_allowed("client1") is True
        assert limiter.is_allowed("client1") is False

        # Simulate time passing
        limiter._buckets["client1"] = (0.0, time.time() - 2)
        assert limiter.is_allowed("client1") is True

    def test_get_remaining(self):
        limiter = TokenBucketRateLimiter(requests_per_window=5, window_seconds=60)
        limiter.is_allowed("client1")
        remaining = limiter.get_remaining("client1")
        assert remaining == 4

    def test_get_reset_time(self):
        limiter = TokenBucketRateLimiter(requests_per_window=10, window_seconds=60)
        for _ in range(10):
            limiter.is_allowed("client1")
        reset = limiter.get_reset_time("client1")
        assert reset > 0

    def test_thread_safety(self):
        limiter = TokenBucketRateLimiter(requests_per_window=100, window_seconds=60)
        results = []

        def make_requests():
            for _ in range(20):
                results.append(limiter.is_allowed("client1"))

        threads = [threading.Thread(target=make_requests) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        allowed = sum(1 for r in results if r)
        assert allowed == 100  # Exactly 100 tokens available
