import time
from collections import OrderedDict
from typing import Any, Dict, Optional

import imagehash
from PIL import Image


class ImageCache:
    """Cache for analyzed images to avoid re-processing"""

    def __init__(self, max_size: int = 100, ttl: int = 300):
        """
        Initialize image cache.

        Args:
            max_size: Maximum number of entries in cache
            ttl: Time-to-live in seconds for cache entries
        """
        self.max_size = max_size
        self.ttl = ttl
        self.cache: OrderedDict = OrderedDict()  # {hash: (result, timestamp)}
        self._hits = 0
        self._misses = 0

    def get_image_hash(self, image: Image.Image) -> str:
        """
        Compute perceptual hash of an image.

        Args:
            image: PIL Image object

        Returns:
            str: Perceptual hash string
        """
        # Use average hash for speed
        return str(imagehash.average_hash(image, hash_size=16))

    def get(self, image: Image.Image) -> Optional[Dict[str, Any]]:
        """
        Check if image result is in cache.

        Args:
            image: PIL Image object

        Returns:
            dict or None: Cached result or None if not found/expired
        """
        img_hash = self.get_image_hash(image)

        if img_hash in self.cache:
            result, timestamp = self.cache[img_hash]

            # Check if expired
            if time.time() - timestamp < self.ttl:
                # Move to end (most recently used)
                self.cache.move_to_end(img_hash)
                self._hits += 1
                return result
            else:
                # Expired, remove
                del self.cache[img_hash]

        self._misses += 1
        return None

    def set(self, image: Image.Image, result: Dict[str, Any]) -> str:
        """
        Store result in cache.

        Args:
            image: PIL Image object
            result: Analysis result dict

        Returns:
            str: Image hash
        """
        img_hash = self.get_image_hash(image)

        # Remove oldest if at capacity
        while len(self.cache) >= self.max_size:
            self.cache.popitem(last=False)

        self.cache[img_hash] = (result, time.time())
        return img_hash

    def clear(self):
        """Clear all cached entries"""
        self.cache.clear()
        self._hits = 0
        self._misses = 0

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            dict: Cache statistics including hits, misses, and hit rate
        """
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0.0

        return {
            'size': len(self.cache),
            'max_size': self.max_size,
            'hits': self._hits,
            'misses': self._misses,
            'hit_rate': round(hit_rate, 2)
        }

    def is_similar(self, image1: Image.Image, image2: Image.Image, threshold: int = 5) -> bool:
        """
        Check if two images are similar.

        Args:
            image1, image2: PIL Image objects
            threshold: Hamming distance threshold

        Returns:
            bool: True if similar
        """
        hash1 = imagehash.average_hash(image1, hash_size=16)
        hash2 = imagehash.average_hash(image2, hash_size=16)
        return hash1 - hash2 < threshold
