import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import sys

# Add parent directory to path  
sys.path.append(str(Path(__file__).parent.parent))

from main import app

client = TestClient(app)

def test_read_main():
    """Test main endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    assert "ClearCut" in response.text

def test_health_check():
    """Test health endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_robots_txt():
    """Test robots.txt"""
    response = client.get("/robots.txt")
    assert response.status_code == 200
    assert "User-agent: *" in response.text

def test_sitemap_xml():
    """Test sitemap.xml"""
    response = client.get("/sitemap.xml")
    assert response.status_code == 200
    assert "<?xml version" in response.text

def test_favicon():
    """Test favicon endpoint"""
    response = client.get("/favicon.ico")
    # Should either return favicon or 404
    assert response.status_code in [200, 404]

@pytest.mark.asyncio
async def test_remove_bg_no_file():
    """Test background removal without file"""
    response = client.post("/remove-bg")
    assert response.status_code == 400
    assert "No image provided" in response.json()["detail"]

def test_api_stats():
    """Test API stats endpoint"""
    response = client.get("/api/stats")
    assert response.status_code == 200
    assert "uptime" in response.json()