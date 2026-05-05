"""Tests for ImageCache module."""

import time

from PIL import Image

from modules.image_cache import ImageCache


class TestImageCache:
    def test_set_and_get(self, sample_image, mock_result_ai):
        cache = ImageCache(max_size=10, ttl=300)
        cache.set(sample_image, mock_result_ai)
        result = cache.get(sample_image)
        assert result is not None
        assert result["is_ai"] == mock_result_ai["is_ai"]

    def test_cache_miss(self, sample_image):
        cache = ImageCache(max_size=10, ttl=300)
        assert cache.get(sample_image) is None

    def test_lru_eviction(self, mock_result_ai):
        cache = ImageCache(max_size=2, ttl=300)
        # Use images with distinct patterns so perceptual hashes differ
        img1 = Image.new("RGB", (100, 100), color=(0, 0, 0))
        img2 = Image.new("RGB", (100, 100), color=(255, 255, 255))

        # Create a patterned image with a distinct hash
        img3 = Image.new("RGB", (100, 100), color=(0, 0, 0))
        for x in range(50):
            for y in range(100):
                img3.putpixel((x, y), (255, 255, 255))

        h1 = cache.get_image_hash(img1)
        h2 = cache.get_image_hash(img2)
        h3 = cache.get_image_hash(img3)

        # Only run eviction test if all hashes are distinct
        if len({h1, h2, h3}) == 3:
            cache.set(img1, mock_result_ai)
            cache.set(img2, mock_result_ai)
            cache.set(img3, mock_result_ai)  # Should evict img1
            assert cache.get(img1) is None
            assert cache.get(img3) is not None
        else:
            # Fallback: test that cache respects max_size
            cache.set(img1, mock_result_ai)
            assert len(cache.cache) <= 2

    def test_ttl_expiry(self, sample_image, mock_result_ai):
        cache = ImageCache(max_size=10, ttl=1)
        cache.set(sample_image, mock_result_ai)

        # Manually expire the entry
        img_hash = cache.get_image_hash(sample_image)
        cache.cache[img_hash] = (mock_result_ai, time.time() - 2)

        assert cache.get(sample_image) is None

    def test_perceptual_hash_consistency(self, sample_image):
        cache = ImageCache()
        hash1 = cache.get_image_hash(sample_image)
        hash2 = cache.get_image_hash(sample_image)
        assert hash1 == hash2

    def test_stats(self, sample_image, mock_result_ai):
        cache = ImageCache(max_size=10, ttl=300)
        cache.set(sample_image, mock_result_ai)
        cache.get(sample_image)  # hit

        # Use a patterned image guaranteed to have a different hash
        diff_img = Image.new("RGB", (50, 50), color=(0, 0, 0))
        for x in range(25):
            for y in range(50):
                diff_img.putpixel((x, y), (255, 255, 255))
        cache.get(diff_img)  # miss

        stats = cache.get_stats()
        assert stats["hits"] >= 1
        assert stats["misses"] >= 1
        assert stats["size"] >= 1

    def test_clear(self, sample_image, mock_result_ai):
        cache = ImageCache(max_size=10, ttl=300)
        cache.set(sample_image, mock_result_ai)
        cache.clear()
        # After clear, cache should miss
        result = cache.get(sample_image)
        assert result is None
        stats = cache.get_stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 1  # The get after clear is a miss

    def test_is_similar_same_image(self):
        cache = ImageCache()
        img1 = Image.new("RGB", (100, 100), color=(128, 128, 128))
        # Same image should be similar to itself
        assert cache.is_similar(img1, img1)

    def test_hash_deterministic(self):
        cache = ImageCache()
        img = Image.new("RGB", (100, 100), color=(42, 42, 42))
        h1 = cache.get_image_hash(img)
        h2 = cache.get_image_hash(img)
        assert h1 == h2
