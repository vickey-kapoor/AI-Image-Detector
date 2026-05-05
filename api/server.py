"""FastAPI server for AI Image Detector."""

import asyncio
import base64
import io
import ipaddress
import logging
import socket
import uuid
from contextlib import asynccontextmanager
from typing import List, Optional
from urllib.parse import urlparse

import httpx

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from PIL import Image
from pydantic import BaseModel, Field, field_validator

from api.config import get_settings
from api.rate_limiter import TokenBucketRateLimiter
from modules.ai_detector import AIImageDetector
from modules.image_cache import ImageCache
from modules.json_logger import JSONLogger

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("ai_detector")

# Global instances
detector: Optional[AIImageDetector] = None
cache: Optional[ImageCache] = None
json_logger: Optional[JSONLogger] = None
rate_limiter: Optional[TokenBucketRateLimiter] = None

VERSION = "1.1.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global detector, cache, json_logger, rate_limiter

    settings = get_settings()

    # Initialize components
    logger.info("Initializing AI Image Detector API...")

    json_logger = JSONLogger(
        log_dir=settings.log_dir,
        retention_days=settings.log_retention_days
    )

    cache = ImageCache(
        max_size=settings.cache_max_size,
        ttl=settings.cache_ttl_seconds
    )

    rate_limiter = TokenBucketRateLimiter(
        requests_per_window=settings.rate_limit_requests,
        window_seconds=settings.rate_limit_window_seconds
    )

    detector = AIImageDetector()

    # Warm up model with dummy inference
    logger.info("Warming up model...")
    dummy_image = Image.new("RGB", (224, 224), color=(128, 128, 128))
    await asyncio.to_thread(detector.analyze_image, dummy_image)
    logger.info("Model warm-up complete!")

    logger.info("API initialization complete!")

    yield

    # Cleanup
    logger.info("Shutting down API...")


app = FastAPI(
    title="AI Image Detector API",
    description="Detect AI-generated images using ViT classifier (94.2% accuracy)",
    version=VERSION,
    lifespan=lifespan
)

# Configure CORS
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Authentication ---

async def verify_api_key(x_api_key: Optional[str] = Header(None)):
    """Dependency that checks X-API-Key header when API_KEY is configured."""
    api_key = get_settings().api_key
    if not api_key:
        return  # Auth disabled
    if x_api_key != api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


# --- Request/Response models ---

class AnalyzeRequest(BaseModel):
    """Request model for image analysis."""
    image_base64: str = Field(..., description="Base64-encoded image data")
    source_url: str = Field(..., description="URL of the page containing the image")
    image_url: Optional[str] = Field(None, description="URL of the image itself")

    @field_validator("image_base64")
    @classmethod
    def validate_image_size(cls, v):
        max_size = get_settings().max_image_size_mb * 1024 * 1024
        # Base64 is ~4/3 the size of the raw data
        estimated_size = len(v) * 3 / 4
        if estimated_size > max_size:
            raise ValueError(
                f"Image exceeds maximum size of {get_settings().max_image_size_mb}MB"
            )
        return v


class AnalyzeResponse(BaseModel):
    """Response model for image analysis."""
    request_id: str
    is_ai: bool
    confidence: float
    verdict: str
    fake_probability: float
    real_probability: float
    image_hash: str
    processing_time_ms: float
    cached: bool


class BatchAnalyzeRequest(BaseModel):
    """Request model for batch image analysis."""
    images: List[AnalyzeRequest] = Field(..., min_length=1, max_length=10)


class BatchAnalyzeResponse(BaseModel):
    """Response model for batch analysis."""
    results: List[AnalyzeResponse]


class UrlAnalyzeRequest(BaseModel):
    """Request model for URL-based analysis."""
    image_url: str = Field(..., description="URL of the image to analyze")
    source_url: str = Field("", description="URL of the page containing the image")


class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str
    model_loaded: bool
    device: str
    version: str


class StatsResponse(BaseModel):
    """Response model for statistics."""
    total_analyses: int
    ai_detections: int
    cache_hits: int
    cache_hit_rate: float


# --- Helpers ---

def get_client_ip(request: Request) -> str:
    """Extract client IP from request."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def _analyze_single(image: Image.Image, source_url: str, image_url: Optional[str]) -> AnalyzeResponse:
    """Shared analysis logic for single image."""
    global detector, cache, json_logger

    request_id = str(uuid.uuid4())

    # Check cache
    cached_result = cache.get(image)
    cache_hit = cached_result is not None

    if cache_hit:
        result = cached_result
        image_hash = cache.get_image_hash(image)
        processing_time_ms = 0.0
    else:
        # Analyze image asynchronously to avoid blocking the event loop
        result = await asyncio.to_thread(detector.analyze_image, image)
        processing_time_ms = result.get("processing_time_ms", 0.0)

        # Cache result
        image_hash = cache.set(image, result)

    # Log analysis
    model_info = detector.get_model_info()
    json_logger.log_analysis(
        request_id=request_id,
        image_hash=image_hash,
        source_url=source_url,
        result=result,
        processing_time_ms=processing_time_ms,
        model_info=model_info,
        cache_hit=cache_hit,
        image_url=image_url
    )

    return AnalyzeResponse(
        request_id=request_id,
        is_ai=result["is_ai"],
        confidence=result["confidence"],
        verdict=result["verdict"],
        fake_probability=result["fake_probability"],
        real_probability=result["real_probability"],
        image_hash=image_hash,
        processing_time_ms=processing_time_ms,
        cached=cache_hit
    )


_ALLOWED_SCHEMES = {"http", "https"}


async def _validate_url_ssrf(url: str) -> None:
    """Raise 400 if the URL targets a private/reserved address (SSRF prevention)."""
    try:
        parsed = urlparse(url)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid URL")

    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise HTTPException(status_code=400, detail="Only http and https URLs are allowed")

    hostname = parsed.hostname
    if not hostname:
        raise HTTPException(status_code=400, detail="Invalid URL: missing hostname")

    try:
        # Resolve in a thread — getaddrinfo is blocking
        addr_infos = await asyncio.to_thread(socket.getaddrinfo, hostname, None)
    except socket.gaierror:
        raise HTTPException(status_code=400, detail=f"Could not resolve hostname: {hostname}")

    for addr_info in addr_infos:
        ip = ipaddress.ip_address(addr_info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise HTTPException(status_code=400, detail="URL resolves to a disallowed address")


# --- Endpoints ---

@app.post("/analyze", response_model=AnalyzeResponse, dependencies=[Depends(verify_api_key)])
async def analyze_image(request: Request, body: AnalyzeRequest):
    """
    Analyze an image for AI-generation detection.

    Returns detection results including confidence scores and verdict.
    """
    global detector, cache, json_logger, rate_limiter

    if not detector or not cache or not json_logger or not rate_limiter:
        raise HTTPException(status_code=503, detail="Service not ready")

    # Rate limiting
    client_ip = get_client_ip(request)
    if not rate_limiter.is_allowed(client_ip):
        remaining = rate_limiter.get_remaining(client_ip)
        reset_time = rate_limiter.get_reset_time(client_ip)
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Try again in {reset_time:.0f} seconds.",
            headers={
                "X-RateLimit-Remaining": str(remaining),
                "X-RateLimit-Reset": str(int(reset_time))
            }
        )

    try:
        image_data = base64.b64decode(body.image_base64)
        image = Image.open(io.BytesIO(image_data))
    except Exception as e:
        logger.error(f"Failed to decode image: {e}")
        raise HTTPException(status_code=400, detail="Invalid image data")

    return await _analyze_single(image, body.source_url, body.image_url)


@app.post("/analyze/batch", response_model=BatchAnalyzeResponse, dependencies=[Depends(verify_api_key)])
async def analyze_batch(request: Request, body: BatchAnalyzeRequest):
    """
    Analyze up to 10 images in a single request.

    Images are processed concurrently via thread pool.
    """
    global detector, cache, json_logger, rate_limiter

    if not detector or not cache or not json_logger or not rate_limiter:
        raise HTTPException(status_code=503, detail="Service not ready")

    # Rate limiting (costs N tokens for N images — checked atomically to avoid partial consumption)
    client_ip = get_client_ip(request)
    if not rate_limiter.consume_n(client_ip, len(body.images)):
        remaining = rate_limiter.get_remaining(client_ip)
        reset_time = rate_limiter.get_reset_time(client_ip)
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Try again in {reset_time:.0f} seconds.",
            headers={
                "X-RateLimit-Remaining": str(remaining),
                "X-RateLimit-Reset": str(int(reset_time))
            }
        )

    async def process_one(item: AnalyzeRequest) -> AnalyzeResponse:
        try:
            image_data = base64.b64decode(item.image_base64)
            image = Image.open(io.BytesIO(image_data))
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid image data in batch")
        return await _analyze_single(image, item.source_url, item.image_url)

    results = await asyncio.gather(*[process_one(item) for item in body.images])
    return BatchAnalyzeResponse(results=list(results))


@app.post("/analyze/url", response_model=AnalyzeResponse, dependencies=[Depends(verify_api_key)])
async def analyze_url(request: Request, body: UrlAnalyzeRequest):
    """
    Analyze an image by URL. Server fetches the image, avoiding client-side base64 encoding.
    """
    global detector, cache, json_logger, rate_limiter

    await _validate_url_ssrf(body.image_url)

    if not detector or not cache or not json_logger or not rate_limiter:
        raise HTTPException(status_code=503, detail="Service not ready")

    client_ip = get_client_ip(request)
    if not rate_limiter.is_allowed(client_ip):
        remaining = rate_limiter.get_remaining(client_ip)
        reset_time = rate_limiter.get_reset_time(client_ip)
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Try again in {reset_time:.0f} seconds.",
            headers={
                "X-RateLimit-Remaining": str(remaining),
                "X-RateLimit-Reset": str(int(reset_time))
            }
        )

    max_size = get_settings().max_image_size_mb * 1024 * 1024
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(body.image_url)
            resp.raise_for_status()
            if len(resp.content) > max_size:
                raise HTTPException(
                    status_code=400,
                    detail=f"Image exceeds maximum size of {get_settings().max_image_size_mb}MB"
                )
            image = Image.open(io.BytesIO(resp.content))
    except httpx.HTTPError as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch image: {e}")

    return await _analyze_single(image, body.source_url, body.image_url)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check API health and model status."""
    global detector

    model_loaded = detector is not None
    device = detector.device if detector else "unknown"

    return HealthResponse(
        status="healthy" if model_loaded else "degraded",
        model_loaded=model_loaded,
        device=device,
        version=VERSION
    )


@app.get("/stats", response_model=StatsResponse)
async def get_stats():
    """Get API statistics."""
    global json_logger, cache

    if not json_logger:
        raise HTTPException(status_code=503, detail="Service not ready")

    log_stats = json_logger.get_stats()
    cache_stats = cache.get_stats() if cache else {}

    return StatsResponse(
        total_analyses=log_stats.get("total_analyses", 0),
        ai_detections=log_stats.get("ai_detections", 0),
        cache_hits=cache_stats.get("hits", 0),
        cache_hit_rate=cache_stats.get("hit_rate", 0.0)
    )


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    """Serve analytics dashboard."""
    global json_logger, cache

    log_stats = json_logger.get_stats() if json_logger else {}
    cache_stats = cache.get_stats() if cache else {}
    recent = json_logger.get_recent_entries(20) if json_logger else []

    total = log_stats.get("total_analyses", 0)
    ai = log_stats.get("ai_detections", 0)
    real = total - ai
    cache_hit_rate = cache_stats.get("hit_rate", 0.0)

    # Build recent entries JSON for chart
    import json
    recent_json = json.dumps(recent)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Image Detector - Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f8f9fa; color: #212529; padding: 24px; }}
  h1 {{ font-size: 24px; margin-bottom: 24px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; }}
  .card {{ background: white; border-radius: 12px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
  .card h3 {{ font-size: 13px; color: #6c757d; margin-bottom: 8px; text-transform: uppercase; }}
  .card .value {{ font-size: 32px; font-weight: 700; }}
  .charts {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 24px; }}
  .chart-card {{ background: white; border-radius: 12px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
  .chart-card h3 {{ margin-bottom: 12px; font-size: 16px; }}
  table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
  th, td {{ padding: 10px 14px; text-align: left; border-bottom: 1px solid #e9ecef; font-size: 13px; }}
  th {{ background: #f8f9fa; font-weight: 600; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; }}
  .badge-ai {{ background: #f8d7da; color: #721c24; }}
  .badge-real {{ background: #d4edda; color: #155724; }}
  .badge-uncertain {{ background: #fff3cd; color: #856404; }}
  @media (max-width: 768px) {{ .charts {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>
<h1>AI Image Detector Dashboard</h1>
<div class="grid">
  <div class="card"><h3>Total Analyses</h3><div class="value">{total}</div></div>
  <div class="card"><h3>AI Detected</h3><div class="value" style="color:#dc3545">{ai}</div></div>
  <div class="card"><h3>Real Images</h3><div class="value" style="color:#28a745">{real}</div></div>
  <div class="card"><h3>Cache Hit Rate</h3><div class="value">{cache_hit_rate:.1f}%</div></div>
</div>
<div class="charts">
  <div class="chart-card"><h3>Detection Distribution</h3><canvas id="pieChart"></canvas></div>
  <div class="chart-card"><h3>Processing Time (recent)</h3><canvas id="timeChart"></canvas></div>
</div>
<h2 style="font-size:18px;margin-bottom:12px;">Recent Analyses</h2>
<table>
<thead><tr><th>Time</th><th>Verdict</th><th>Confidence</th><th>Processing</th><th>Cached</th></tr></thead>
<tbody id="recentBody"></tbody>
</table>
<script>
const recent = {recent_json};
// Pie chart
new Chart(document.getElementById('pieChart'), {{
  type: 'doughnut',
  data: {{
    labels: ['AI Detected', 'Real'],
    datasets: [{{ data: [{ai}, {real}], backgroundColor: ['#dc3545', '#28a745'] }}]
  }},
  options: {{ responsive: true, plugins: {{ legend: {{ position: 'bottom' }} }} }}
}});
// Processing time chart
const times = recent.filter(e => !e.cache_hit).map(e => e.processing_time_ms).reverse().slice(-20);
new Chart(document.getElementById('timeChart'), {{
  type: 'line',
  data: {{
    labels: times.map((_, i) => i + 1),
    datasets: [{{ label: 'ms', data: times, borderColor: '#007bff', tension: 0.3, fill: false }}]
  }},
  options: {{ responsive: true, scales: {{ y: {{ beginAtZero: true }} }} }}
}});
// Recent table
const tbody = document.getElementById('recentBody');
recent.slice(0, 20).forEach(e => {{
  const r = e.result || {{}};
  const verdict = r.verdict || 'Unknown';
  const cls = verdict.includes('AI') ? 'ai' : verdict.includes('Real') ? 'real' : 'uncertain';
  const time = e.timestamp ? new Date(e.timestamp).toLocaleString() : '-';
  tbody.innerHTML += '<tr><td>' + time + '</td><td><span class="badge badge-' + cls + '">' + verdict + '</span></td><td>' + ((r.confidence||0)*100).toFixed(1) + '%</td><td>' + (e.processing_time_ms||0).toFixed(0) + 'ms</td><td>' + (e.cache_hit ? 'Yes' : 'No') + '</td></tr>';
}});
</script>
</body>
</html>"""
    return HTMLResponse(content=html)


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "api.server:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True
    )
