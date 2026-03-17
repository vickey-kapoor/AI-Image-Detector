"""Tests for JSONLogger module."""

import json
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from modules.json_logger import JSONLogger


class TestJSONLogger:
    def test_log_analysis_creates_file(self, mock_result_ai):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = JSONLogger(log_dir=tmpdir, retention_days=30)
            logger.log_analysis(
                request_id="test-123",
                image_hash="abc123",
                source_url="https://example.com",
                result=mock_result_ai,
                processing_time_ms=42.5,
                model_info={"name": "test", "device": "cpu", "accuracy": "94.2%"},
                cache_hit=False,
            )
            log_files = list(Path(tmpdir).glob("ai_detector_*.jsonl"))
            assert len(log_files) == 1

    def test_log_entry_format(self, mock_result_ai):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = JSONLogger(log_dir=tmpdir, retention_days=30)
            logger.log_analysis(
                request_id="test-456",
                image_hash="def456",
                source_url="https://example.com",
                result=mock_result_ai,
                processing_time_ms=42.5,
                model_info={"name": "test", "device": "cpu", "accuracy": "94.2%"},
                cache_hit=True,
            )

            log_file = list(Path(tmpdir).glob("ai_detector_*.jsonl"))[0]
            with open(log_file) as f:
                entry = json.loads(f.readline())

            assert entry["request_id"] == "test-456"
            assert entry["image_hash"] == "def456"
            assert entry["cache_hit"] is True
            assert entry["result"]["is_ai"] is True
            assert "timestamp" in entry

    def test_get_stats(self, mock_result_ai, mock_result_real):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = JSONLogger(log_dir=tmpdir, retention_days=30)
            model_info = {"name": "test", "device": "cpu", "accuracy": "94.2%"}

            logger.log_analysis("r1", "h1", "url1", mock_result_ai, 10, model_info, False)
            logger.log_analysis("r2", "h2", "url2", mock_result_real, 20, model_info, False)
            logger.log_analysis("r3", "h3", "url3", mock_result_ai, 5, model_info, True)

            stats = logger.get_stats()
            assert stats["total_analyses"] == 3
            assert stats["ai_detections"] == 2
            assert stats["cache_hits"] == 1

    def test_get_recent_entries(self, mock_result_ai):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = JSONLogger(log_dir=tmpdir, retention_days=30)
            model_info = {"name": "test", "device": "cpu", "accuracy": "94.2%"}

            for i in range(5):
                logger.log_analysis(f"r{i}", f"h{i}", "url", mock_result_ai, 10, model_info, False)

            entries = logger.get_recent_entries(3)
            assert len(entries) == 3

    def test_retention_cleanup(self, mock_result_ai):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = JSONLogger(log_dir=tmpdir, retention_days=1)

            # Create an old log file
            old_date = (datetime.now(UTC) - timedelta(days=5)).strftime("%Y-%m-%d")
            old_file = Path(tmpdir) / f"ai_detector_{old_date}.jsonl"
            old_file.write_text('{"test": true}\n')

            # Trigger cleanup
            logger._cleanup_old_logs()

            assert not old_file.exists()
