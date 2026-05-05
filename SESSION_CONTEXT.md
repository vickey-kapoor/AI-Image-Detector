# Session Context - AI Image Detector

## Last Session: 2026-02-27

### What Was Done

1. **Explored codebase** - AI image detection system with desktop monitor + browser extension

2. **Switched from SigLIP to CLIP** (user request)
   - CLIP zero-shot had ~50% accuracy (basically random)
   - Not effective for AI detection

3. **Switched to umm-maybe/AI-image-detector** (better model)
   - 94.2% accuracy
   - ViT/Swin-based classifier
   - Labels: `artificial` / `human`
   - Created `modules/ai_detector.py`

4. **Cleaned up codebase**
   - Deleted unused files: `clip_detector.py`, `deepfake_detector.py`, `build_database.py`, `reference_images/`
   - Removed legacy KNN code
   - Simplified README

5. **Merged PR #10** into main
   - Branch `feature/browser-extension-api` deleted
   - Main branch is up to date

### Current State

- **Model**: `umm-maybe/AI-image-detector` (94.2% accuracy)
- **Branch**: `main` (up to date)
- **Code**: Ready to run

### Pending Task

**Old CLIP server still running on port 8000** - needs manual kill before starting new server.

To fix:
```powershell
Stop-Process -Name python -Force
```

Then start API:
```bash
cd AI-Image-Detector
.venv\Scripts\activate
python -m uvicorn api.server:app --host 127.0.0.1 --port 8000
```

### Project Structure

```
├── api/
│   ├── server.py          # FastAPI backend (uses AIImageDetector)
│   ├── config.py
│   └── rate_limiter.py
├── modules/
│   ├── ai_detector.py     # ViT model (umm-maybe/AI-image-detector)
│   ├── image_cache.py
│   ├── json_logger.py
│   └── ...
├── extension/             # Chrome MV3 extension
├── screen_monitor_clip.py # Desktop app
└── requirements.txt
```

### Test Results (umm-maybe model)

| Image | Verdict | AI Prob | Human Prob |
|-------|---------|---------|------------|
| Icon | Likely Real | 5.1% | 94.9% |
| Gradient | Likely Real | 21.9% | 78.1% |

### Key Files Changed

- `modules/ai_detector.py` - New ViT-based detector
- `api/server.py` - Uses AIImageDetector
- `screen_monitor_clip.py` - Uses AIImageDetector
- `README.md` - Updated docs

### Links

- Repo: https://github.com/vickey-kapoor/AI-Image-Detector
- Model: https://huggingface.co/umm-maybe/AI-image-detector
