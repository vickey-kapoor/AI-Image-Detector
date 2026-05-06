# AI Image Detector

Detect AI-generated images using a ViT-based classifier with **94.2% accuracy**. Three modes of use: a **FastAPI backend**, a **Chrome extension**, and a **desktop system tray monitor**.

## Features

- **High accuracy** — ViT classifier (`umm-maybe/AI-image-detector`) trained on AI vs human-created images
- **Three verdicts** — Likely AI / Uncertain / Likely Real, with per-class probability scores
- **Browser extension** — auto-scans images on any web page with visual badge overlays
- **System tray monitor** — silent background monitoring of your screen; Windows toast notification + sound on AI detection
- **REST API** — single image, batch (up to 10), or server-side URL fetch; rate limiting, perceptual hash cache, JSONL logging
- **Analytics dashboard** — live stats at `/dashboard`
- **Docker support** — single `docker-compose up` to run the API

---

## Quick Start

### Option 1: Browser Extension

**1. Start the backend API:**
```bash
pip install -r requirements.txt
python -m uvicorn api.server:app --host 127.0.0.1 --port 8000
```

**2. Load the extension in Chrome:**
- Go to `chrome://extensions/`
- Enable "Developer mode"
- Click "Load unpacked" and select the `extension/` folder

**3. Browse the web** — images are automatically scanned with confidence badge overlays.

### Option 2: Desktop System Tray Monitor

```bash
pip install -r requirements.txt
python screen_monitor.py
```

The app runs silently in the system tray (no window). Right-click the tray icon to start/stop monitoring, view session stats, or quit. The icon turns green while monitoring. A toast notification and alert sound fire whenever an AI-generated screen image is detected.

### Option 3: Docker

```bash
docker-compose up
```

API available at `http://localhost:8000`.

---

## API

All `/analyze*` endpoints require an `X-API-Key` header when the `API_KEY` environment variable is set. `/health`, `/stats`, and `/dashboard` are always public.

### Endpoints

| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `/analyze` | POST | ✓ | Analyze a base64-encoded image |
| `/analyze/batch` | POST | ✓ | Analyze up to 10 images in one request |
| `/analyze/url` | POST | ✓ | Analyze an image by URL (server-side fetch) |
| `/health` | GET | — | Model status and API version |
| `/stats` | GET | — | Aggregate detection statistics |
| `/dashboard` | GET | — | Live analytics dashboard |

### Example

```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-key" \
  -d '{"image_base64": "<base64>", "source_url": "https://example.com"}'
```

```json
{
  "request_id": "3f2a1b...",
  "is_ai": true,
  "confidence": 0.91,
  "verdict": "Likely AI",
  "fake_probability": 0.91,
  "real_probability": 0.09,
  "image_hash": "f8a0...",
  "processing_time_ms": 148.3,
  "cached": false
}
```

### Batch

```bash
curl -X POST http://localhost:8000/analyze/batch \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-key" \
  -d '{"images": [{"image_base64": "<base64>", "source_url": "https://example.com"}, ...]}'
```

Rate limiting for batch is atomic — N images consume N tokens, or the whole request is rejected if fewer than N tokens remain.

---

## Configuration

All settings are environment variables (or a `.env` file).

| Variable | Default | Description |
|---|---|---|
| `API_KEY` | *(empty — auth disabled)* | Require this key on `/analyze*` endpoints |
| `API_HOST` | `127.0.0.1` | Bind address |
| `API_PORT` | `8000` | Port |
| `CORS_ORIGINS` | `chrome-extension://*` | Comma-separated allowed origins; set `*` for open access |
| `RATE_LIMIT_REQUESTS` | `30` | Max requests per window per IP |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Rate limit window duration |
| `CACHE_MAX_SIZE` | `100` | Max cached image results (LRU) |
| `CACHE_TTL_SECONDS` | `300` | Cache entry lifetime |
| `MAX_IMAGE_SIZE_MB` | `10` | Max accepted image size |
| `LOG_DIR` | `./logs` | JSONL log output directory |
| `LOG_RETENTION_DAYS` | `30` | Days to keep log files |

---

## Testing

```bash
pip install -r requirements-dev.txt

# Fast suite — no model download, runs in ~2s
pytest tests/ -v

# Full suite — uses the real ViT model (~400MB download on first run)
pytest tests/ -v --real-model
```

| Test file | What it covers |
|---|---|
| `test_ai_detector.py` | Inference wrapper, resize, verdict thresholds (mocked) |
| `test_api.py` | All API endpoints, auth, rate limiting (mocked) |
| `test_monitor_controller.py` | Desktop monitor loop, cache, notifications (mocked) |
| `test_image_cache.py` | LRU cache, perceptual hash deduplication, TTL |
| `test_json_logger.py` | JSONL logging, daily rotation |
| `test_rate_limiter.py` | Token bucket logic, atomic batch consumption |
| `test_real_pipeline.py` | Real ViT inference — requires `--real-model` |
| `test_e2e_api.py` | Full API → model path, caching — requires `--real-model` |

---

## Project Structure

```
├── api/
│   ├── server.py          # FastAPI app, endpoints, SSRF-safe URL fetch
│   ├── config.py          # Pydantic Settings
│   └── rate_limiter.py    # Token bucket (per IP, thread-safe)
│
├── extension/             # Chrome MV3 extension (vanilla JS, no build step)
│   ├── manifest.json
│   ├── background/        # Service worker
│   ├── content/           # Content script + styles
│   ├── popup/             # Toolbar popup
│   ├── options/           # API key settings page
│   └── utils/             # API client wrapper
│
├── modules/
│   ├── ai_detector.py     # ViT pipeline wrapper (umm-maybe/AI-image-detector)
│   ├── image_cache.py     # Perceptual-hash LRU cache
│   ├── json_logger.py     # JSONL logger with daily rotation
│   ├── notifier.py        # Toast notifications + alert sound (plyer + winsound)
│   └── screen_capture.py  # MSS screen capture
│
├── tests/                 # pytest suite (70 tests)
├── screen_monitor.py # Desktop system tray entry point
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── requirements-dev.txt
```

---

## Model Details

Uses [umm-maybe/AI-image-detector](https://huggingface.co/umm-maybe/AI-image-detector):

- **Architecture**: Vision Transformer (ViT/Swin)
- **Accuracy**: 94.2%
- **Labels**: `artificial` (AI-generated) / `human` (real photograph)
- **Verdict thresholds**: score > 0.6 → confident verdict; otherwise "Uncertain"
- **First run**: downloads ~400 MB to `~/.cache/huggingface/`

### Limitations

- Optimised for artistic images (paintings, illustrations, AI art)
- May not perform as well on photorealistic deepfakes
- Training data predates Midjourney v5, SDXL, and DALL-E 3

---

## Requirements

- Python 3.11+
- Chrome (for the browser extension)
- CUDA GPU optional — CPU inference works, just slower
- Windows recommended for the desktop monitor (`winsound` / `pystray`)

---

## License

MIT
