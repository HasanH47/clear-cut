from fastapi import FastAPI, File, UploadFile, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
import tempfile
import asyncio
import aiofiles
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
        
        # Generate cache key
        cache_key = generate_cache_key(content)
        
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
