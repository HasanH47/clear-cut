from fastapi import FastAPI, File, UploadFile, HTTPException, Request, Form, Response
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
import asyncio
from typing import Optional
import magic
from PIL import Image
import io
import logging
from pathlib import Path
import hashlib
import time
from urllib.parse import urlparse
import aiohttp
from contextlib import asynccontextmanager
from datetime import datetime

from bg_remover import BackgroundRemover

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", 10 * 1024 * 1024))  # 10MB
ALLOWED_EXTENSIONS = os.getenv("ALLOWED_EXTENSIONS", "jpg,jpeg,png,webp").split(",")
TEMP_DIR = os.getenv("TEMP_DIR", "/tmp/clearcut")

# Global background remover instance
bg_remover = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global bg_remover
    # Startup
    logger.info("Initializing ClearCut Background Remover...")
    bg_remover = BackgroundRemover()
    await bg_remover.initialize()

    # Ensure temp directory exists
    Path(TEMP_DIR).mkdir(parents=True, exist_ok=True)

    logger.info("ClearCut is ready!")
    yield

    # Shutdown
    logger.info("Shutting down ClearCut...")
    if bg_remover:
        await bg_remover.cleanup()

app = FastAPI(
    title="ClearCut - AI Background Remover",
    description="High-quality background removal with AI - Privacy-first & Open Source",
    version="1.0.0",
    lifespan=lifespan
)

# Templates
templates = Jinja2Templates(directory="templates")

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")

def validate_image_file(file_content: bytes, filename: str) -> bool:
    """Validate if file is a valid image"""
    try:
        # Check file size
        if len(file_content) > MAX_FILE_SIZE:
            return False

        # Check extension
        ext = filename.lower().split('.')[-1]
        if ext not in ALLOWED_EXTENSIONS:
            return False

        # Check magic bytes
        mime = magic.from_buffer(file_content, mime=True)
        if not mime.startswith('image/'):
            return False

        # Try to open with PIL
        Image.open(io.BytesIO(file_content))
        return True
    except Exception:
        return False

async def download_image_from_url(url: str) -> tuple[bytes, str]:
    """Download image from URL"""
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError("Invalid URL")

        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status != 200:
                    raise ValueError(f"Failed to download: HTTP {response.status}")

                content = await response.read()

                # Get filename from URL or use default
                filename = parsed.path.split('/')[-1] or 'image.jpg'
                if '.' not in filename:
                    filename += '.jpg'

                return content, filename
    except Exception as e:
        raise ValueError(f"Failed to download image: {str(e)}")

def generate_cache_key(content: bytes) -> str:
    """Generate cache key from file content"""
    return hashlib.md5(content).hexdigest()[:16]

async def cleanup_temp_files():
    """Cleanup old temp files"""
    try:
        temp_path = Path(TEMP_DIR)
        current_time = time.time()

        for file_path in temp_path.glob("*"):
            if file_path.is_file():
                # Remove files older than 1 hour
                if current_time - file_path.stat().st_mtime > 3600:
                    file_path.unlink()
    except Exception as e:
        logger.error(f"Cleanup error: {e}")

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "ClearCut"}

@app.post("/remove-bg")
async def remove_background(
    request: Request,
    file: Optional[UploadFile] = File(None),
    url: Optional[str] = Form(None)
):
    """Remove background from uploaded file or URL"""
    try:
        # Cleanup old files
        asyncio.create_task(cleanup_temp_files())

        # Get image content
        if file:
            if not file.filename:
                raise HTTPException(status_code=400, detail="No filename provided")

            content = await file.read()
            filename = file.filename
        elif url:
            content, filename = await download_image_from_url(url)
        else:
            raise HTTPException(status_code=400, detail="No file or URL provided")

        # Validate image
        if not validate_image_file(content, filename):
            raise HTTPException(status_code=400, detail="Invalid image file")

        # Process image
        start_time = time.time()
        result_image = await bg_remover.remove_background(content)
        processing_time = time.time() - start_time

        # Convert to bytes
        img_byte_arr = io.BytesIO()
        result_image.save(img_byte_arr, format='PNG', optimize=True)
        result_bytes = img_byte_arr.getvalue()

        logger.info(f"Processed {filename} in {processing_time:.2f}s")

        # Return image
        return StreamingResponse(
            io.BytesIO(result_bytes),
            media_type="image/png",
            headers={
                "Content-Disposition": f"attachment; filename=clearcut_{filename.split('.')[0]}.png",
                "X-Processing-Time": str(processing_time),
                "Cache-Control": "no-cache, no-store, must-revalidate"
            }
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Processing error: {e}")
        raise HTTPException(status_code=500, detail="Failed to process image")

@app.post("/remove-bg-preview")
async def remove_background_preview(
    request: Request,
    file: Optional[UploadFile] = File(None),
    url: Optional[str] = Form(None)
):
    """Remove background and return base64 preview"""
    try:
        # Get image content (same as above)
        if file:
            if not file.filename:
                raise HTTPException(status_code=400, detail="No filename provided")

            content = await file.read()
            filename = file.filename
        elif url:
            content, filename = await download_image_from_url(url)
        else:
            raise HTTPException(status_code=400, detail="No file or URL provided")

        # Validate image
        if not validate_image_file(content, filename):
            raise HTTPException(status_code=400, detail="Invalid image file")

        # Process image
        start_time = time.time()
        result_image = await bg_remover.remove_background(content)
        processing_time = time.time() - start_time

        # Create thumbnail for preview
        result_image.thumbnail((800, 600), Image.Resampling.LANCZOS)

        # Convert to base64
        img_byte_arr = io.BytesIO()
        result_image.save(img_byte_arr, format='PNG', optimize=True)
        img_byte_arr.seek(0)

        import base64
        img_base64 = base64.b64encode(img_byte_arr.getvalue()).decode()

        return JSONResponse({
            "success": True,
            "preview": f"data:image/png;base64,{img_base64}",
            "processing_time": processing_time,
            "original_size": len(content),
            "result_size": len(img_byte_arr.getvalue())
        })

    except ValueError as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=400)
    except Exception as e:
        logger.error(f"Preview error: {e}")
        return JSONResponse({"success": False, "error": "Failed to process image"}, status_code=500)

@app.get("/api/stats")
async def get_stats():
    """Get service statistics"""
    return {
        "service": "ClearCut",
        "version": "1.0.0",
        "model": "u2net",
        "max_file_size": MAX_FILE_SIZE,
        "supported_formats": ALLOWED_EXTENSIONS,
        "privacy": "No data stored - processed in memory only"
    }

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Serve favicon"""
    favicon_path = Path("static/favicon.ico")
    if favicon_path.exists():
        return FileResponse(favicon_path)
    else:
        # Return 404 if favicon not found
        raise HTTPException(status_code=404, detail="Favicon not found")

@app.get("/og-image.png", include_in_schema=False)
async def og_image():
    """Serve og-image"""
    og_image_path = Path("static/og-image.png")
    if og_image_path.exists():
        return FileResponse(og_image_path)
    else:
        # Return 404 if og-image not found
        raise HTTPException(status_code=404, detail="OG Image not found")

@app.get("/twitter-image.png", include_in_schema=False)
async def twitter_image():
    """Serve twitter-image"""
    twitter_image_path = Path("static/twitter-image.png")
    if twitter_image_path.exists():
        return FileResponse(twitter_image_path)
    else:
        # Return 404 if twitter-image not found
        raise HTTPException(status_code=404, detail="Twitter Image not found")

@app.get("/apple-touch-icon.png", include_in_schema=False)
async def apple_touch_icon():
    """Serve apple_touch_icon"""
    apple_touch_icon_path = Path("static/apple-touch-icon.png")
    if apple_touch_icon_path.exists():
        return FileResponse(apple_touch_icon_path)
    else:
        # Return 404 if apple-touch-icon not found
        raise HTTPException(status_code=404, detail="Apple Touch Icon not found")

@app.get("/robots.txt", include_in_schema=False)
async def robots_txt():
    """Serve robots.txt"""
    content = """User-agent: *
Allow: /
Disallow: /api/
Disallow: /remove-bg
Disallow: /remove-bg-preview

Sitemap: https://clearcut.hasanh.dev/sitemap.xml
"""
    return Response(content=content, media_type="text/plain")

@app.get("/sitemap.xml", include_in_schema=False)
async def sitemap_xml():
    """Generate sitemap.xml"""
    base_url = "https://clearcut.hasanh.dev"

    sitemap_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">
    <url>
        <loc>{base_url}/</loc>
        <lastmod>{datetime.now().strftime('%Y-%m-%d')}</lastmod>
        <changefreq>weekly</changefreq>
        <priority>1.0</priority>
        <image:image>
            <image:loc>{base_url}/static/og-image.png</image:loc>
            <image:title>ClearCut AI Background Remover</image:title>
            <image:caption>Free AI-powered background removal tool</image:caption>
        </image:image>
    </url>
    <url>
        <loc>{base_url}/health</loc>
        <lastmod>{datetime.now().strftime('%Y-%m-%d')}</lastmod>
        <changefreq>daily</changefreq>
        <priority>0.3</priority>
    </url>
</urlset>"""

    return Response(content=sitemap_content, media_type="application/xml")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
