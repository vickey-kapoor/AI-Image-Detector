# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview
ViT-based AI image detector (94.2% accuracy) using the `umm-maybe/AI-image-detector` HuggingFace model. Three components: FastAPI backend, Chrome MV3 extension, and Tkinter desktop monitor.

## Setup
```bash
# Install dev dependencies (includes pytest, ruff, httpx)
pip install -r requirements-dev.txt
```

The model (`umm-maybe/AI-image-detector`) downloads ~400MB from HuggingFace on first startup and caches to `~/.cache/huggingface/`.

## Common Commands
```bash
# Start API server (dev with auto-reload)
python -m uvicorn api.server:app --host 127.0.0.1 --port 8000 --reload

# Run all tests
pytest tests/ -v

# Run a single test file
pytest tests/test_api.py -v

# Run a single test by name
pytest tests/test_api.py -k "test_function_name" -v

# Lint
ruff check .

# Lint with auto-fix
ruff check . --fix

# Docker
docker-compose up
```

## Architecture
- **API** (`api/`): FastAPI server with rate limiting, caching, JSON logging. Endpoints: `/analyze`, `/analyze/batch`, `/analyze/url`, `/health`, `/stats`, `/dashboard`.
- **Extension** (`extension/`): Chrome MV3 browser extension with auto-scan and visual overlays. Vanilla JS, no build step.
- **Desktop** (`screen_monitor_clip.py` + `modules/`): Real-time screen capture analysis with Tkinter UI.

### Request flow (API)
1. Request hits `api/server.py` → API key auth via `X-API-Key` header (only `/analyze*` endpoints)
2. Rate limiting via token bucket (`api/rate_limiter.py`)
3. Image decoded → cache check via perceptual hash (`modules/image_cache.py`)
4. On cache miss: inference via `modules/ai_detector.py` wrapped in `asyncio.to_thread()` to stay non-blocking
5. Result logged to JSONL via `modules/json_logger.py`

### Extension → API communication
- Extension stores API key in `chrome.storage.sync`, sends via `X-API-Key` header
- Content script (`extension/content/content-script.js`) does direct fetch to the API (not routed through service worker)
- API client wrapper in `extension/utils/api-client.js`

## Configuration
All settings via environment variables (or `.env` file), defined in `api/config.py` using Pydantic Settings. Key non-obvious defaults:
- `CORS_ORIGINS` defaults to `chrome-extension://*` — set to `http://localhost:*` or `*` for local/browser testing outside the extension
- `RATE_LIMIT_REQUESTS=30` / `RATE_LIMIT_WINDOW_SECONDS=60` — per client IP, token bucket

## Development Conventions
- Model inference uses `asyncio.to_thread()` — never call the classifier directly in an async handler
- Images are resized to max 1024px before classification (constant `MAX_IMAGE_DIMENSION` in `modules/ai_detector.py`)
- Verdict thresholds: `artificial > 0.6` → "Likely AI", `human > 0.6` → "Likely Real", else "Uncertain" (`modules/ai_detector.py:82-93`)
- `/health`, `/stats`, and `/dashboard` are public; `/analyze*` endpoints require API key when `API_KEY` env var is set
- Batch endpoint (`/analyze/batch`) consumes one rate-limit token per image atomically — if the full batch can't be served, no tokens are consumed and 429 is returned
- Perceptual hashing (`imagehash`) for cache deduplication — similar images hit the same cache entry
- Tests mock the HuggingFace pipeline to avoid downloading the model (see `tests/conftest.py` for shared fixtures)
- pytest uses `asyncio_mode = "auto"` — async test functions run automatically without `@pytest.mark.asyncio`
- Ruff config: Python 3.11 target, 120-char line length, E501 ignored (see `pyproject.toml`)

## Known Tech Debt
- Desktop monitor file still named `screen_monitor_clip.py` (legacy from CLIP migration)
- Extension content script does direct fetch instead of routing through service worker
