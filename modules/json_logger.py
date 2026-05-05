"""Structured JSON logging for AI Image Detector API."""

import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Optional


class JSONLogger:
    """Structured JSON logger with daily rotation and retention."""

    def __init__(self, log_dir: str = "./logs", retention_days: int = 30):
        """
        Initialize the JSON logger.

        Args:
            log_dir: Directory to store log files
            retention_days: Number of days to retain log files
        """
        self.log_dir = Path(log_dir)
        self.retention_days = retention_days
        self._lock = Lock()
        self._current_date: Optional[str] = None
        self._current_file: Optional[Path] = None

        # Create log directory if it doesn't exist
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Set up Python logging
        self._setup_python_logging()

        # Clean up old log files on init
        self._cleanup_old_logs()

    def _setup_python_logging(self):
        """Configure Python logging to use this logger."""
        self.logger = logging.getLogger("ai_detector")
        self.logger.setLevel(logging.INFO)

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        console_handler.setFormatter(formatter)

        # Only add handler if not already added
        if not self.logger.handlers:
            self.logger.addHandler(console_handler)

    def _get_log_file_path(self) -> Path:
        """Get the path to the current day's log file."""
        today = datetime.now(UTC).strftime("%Y-%m-%d")

        if self._current_date != today:
            self._current_date = today
            self._current_file = self.log_dir / f"ai_detector_{today}.jsonl"

        return self._current_file

    def _cleanup_old_logs(self):
        """Remove log files older than retention_days."""
        cutoff_date = datetime.now(UTC) - timedelta(days=self.retention_days)

        for log_file in self.log_dir.glob("ai_detector_*.jsonl"):
            try:
                # Extract date from filename
                date_str = log_file.stem.replace("ai_detector_", "")
                file_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=UTC)

                if file_date < cutoff_date:
                    log_file.unlink()
                    self.logger.info(f"Cleaned up old log file: {log_file.name}")
            except (ValueError, OSError) as e:
                self.logger.warning(f"Error processing log file {log_file}: {e}")

    def log_analysis(
        self,
        request_id: str,
        image_hash: str,
        source_url: str,
        result: Dict[str, Any],
        processing_time_ms: float,
        model_info: Dict[str, str],
        cache_hit: bool,
        image_url: Optional[str] = None,
    ):
        """
        Log an analysis result.

        Args:
            request_id: Unique request identifier
            image_hash: Perceptual hash of the analyzed image
            source_url: URL of the page containing the image
            result: Analysis result dictionary
            processing_time_ms: Processing time in milliseconds
            model_info: Model information dictionary
            cache_hit: Whether the result was from cache
            image_url: Optional URL of the image itself
        """
        entry = {
            "timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "request_id": request_id,
            "image_hash": image_hash,
            "source_url": source_url,
            "image_url": image_url,
            "result": {
                "is_ai": result.get("is_ai", False),
                "confidence": result.get("confidence", 0.0),
                "verdict": result.get("verdict", "Unknown"),
                "fake_probability": result.get("fake_probability", 0.0),
                "real_probability": result.get("real_probability", 0.0),
            },
            "processing_time_ms": round(processing_time_ms, 2),
            "model_info": model_info,
            "cache_hit": cache_hit,
        }

        self._write_entry(entry)
        self.logger.info(
            f"Analysis logged: {request_id} - {result.get('verdict', 'Unknown')} "
            f"({processing_time_ms:.1f}ms, cache_hit={cache_hit})"
        )

    def _write_entry(self, entry: Dict[str, Any]):
        """Write a log entry to the current log file."""
        with self._lock:
            log_file = self._get_log_file_path()
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def get_recent_entries(self, count: int = 100) -> list:
        """
        Get the most recent log entries.

        Args:
            count: Maximum number of entries to return

        Returns:
            List of log entries (newest first)
        """
        entries = []
        log_files = sorted(self.log_dir.glob("ai_detector_*.jsonl"), reverse=True)

        for log_file in log_files:
            if len(entries) >= count:
                break

            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    file_entries = [json.loads(line) for line in f if line.strip()]
                    entries.extend(reversed(file_entries))
            except (json.JSONDecodeError, OSError) as e:
                self.logger.warning(f"Error reading log file {log_file}: {e}")

        return entries[:count]

    def get_stats(self) -> Dict[str, Any]:
        """
        Get aggregate statistics from logs.

        Returns:
            Dictionary with analysis statistics
        """
        total_analyses = 0
        ai_detections = 0
        cache_hits = 0

        for log_file in self.log_dir.glob("ai_detector_*.jsonl"):
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        if not line.strip():
                            continue
                        try:
                            entry = json.loads(line)
                            total_analyses += 1
                            if entry.get("result", {}).get("is_ai", False):
                                ai_detections += 1
                            if entry.get("cache_hit", False):
                                cache_hits += 1
                        except json.JSONDecodeError:
                            continue
            except OSError:
                continue

        cache_hit_rate = (cache_hits / total_analyses * 100) if total_analyses > 0 else 0.0

        return {
            "total_analyses": total_analyses,
            "ai_detections": ai_detections,
            "cache_hits": cache_hits,
            "cache_hit_rate": round(cache_hit_rate, 2),
        }
