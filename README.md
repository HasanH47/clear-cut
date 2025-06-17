# ClearCut - AI Background Remover 🎨✂️

**Privacy-first, open-source background removal service powered by machine learning**

![ClearCut Logo](https://img.shields.io/badge/ClearCut-AI%20Background%20Remover-blue?style=for-the-badge&logo=scissors)

## 🚀 Features

- **🤖 AI-Powered**: Uses U²-Net neural network for high-quality background removal
- **🔒 Privacy-First**: No data storage - all processing happens in memory
- **⚡ Lightning Fast**: Average processing time 2-5 seconds
- **📱 Multiple Input Methods**: Drag & drop, file upload, or URL input
- **🎯 High Quality**: Advanced post-processing for professional results
- **🌐 Production Ready**: Optimized for VPS deployment (2 core, 2GB RAM)
- **🔓 Open Source**: Fully transparent and self-hostable

## 🛠️ Tech Stack

- **Backend**: FastAPI (Python)
- **AI Model**: U²-Net via rembg library
- **Image Processing**: OpenCV, PIL, NumPy
- **Frontend**: HTML5, TailwindCSS, Vanilla JavaScript
- **Container**: Podman/Docker
- **Reverse Proxy**: Caddy (recommended)

## 📋 Requirements

- **System**: Linux VPS (2 cores, 2GB RAM minimum)
- **Software**: Podman or Docker
- **Network**: Domain with SSL (for production)

## 🚀 Quick Start

### 1. Clone Repository
```bash
git clone https://github.com/HasanH47/clear-cut.git
cd clearcut
```

### 2. Deploy with Podman
```bash
# Build and run with podman-compose
podman-compose up -d

# Or manually with podman
podman build -t clearcut .
podman run -d --name clearcut -p 127.0.0.1:8000:8000 clearcut
```

### 3. Configure Reverse Proxy (Caddy)
Add to your Caddyfile:
```caddy
clearcut.hasanh.dev {
    reverse_proxy localhost:8000

    # Security headers
    header {
        X-Content-Type-Options nosniff
        X-Frame-Options DENY
        X-XSS-Protection "1; mode=block"
        Referrer-Policy strict-origin-when-cross-origin
    }

    # Rate limiting (optional)
    rate_limit {
        zone clearcut
        key {remote_host}
        events 30
        window 1m
    }
}
```

### 4. Reload Caddy
```bash
sudo systemctl reload caddy
```

## 🔧 Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_FILE_SIZE` | 10485760 | Maximum file size in bytes (10MB) |
| `ALLOWED_EXTENSIONS` | jpg,jpeg,png,webp | Comma-separated allowed extensions |
| `TEMP_DIR` | /tmp/clearcut | Temporary directory for processing |

### Resource Limits

The service is optimized for a 2-core, 2GB RAM VPS:
- **Memory Limit**: 1.5GB container limit
- **CPU Limit**: 1.8 cores
- **ONNX Runtime**: Configured for CPU optimization
- **Thread Pool**: Limited to 2 threads for image processing

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│                 │    │                 │    │                 │
│   Caddy Proxy   │───▶│  FastAPI App    │───▶│  U²-Net Model   │
│  (SSL + Rate    │    │ (Python Backend)│    │ (Background     │
│   Limiting)     │    │                 │    │  Removal AI)    │
│                 │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         ▲                       │                       │
         │                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│                 │    │                 │    │                 │
│   Web Browser   │    │  Image Pipeline │    │ Post-Processing │
│ (Drag & Drop UI)│    │ (OpenCV + PIL)  │    │ (Edge Enhancement│
│                 │    │                 │    │  + Cleanup)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 📁 Project Structure

```
clearcut/
├── main.py                 # FastAPI application
├── bg_remover.py          # Background removal logic
├── templates/
│   └── index.html         # Web interface
├── requirements.txt       # Python dependencies
├── Dockerfile            # Container configuration
├── podman-compose.yml    # Deployment configuration
└── README.md            # This file
```

## 🔒 Privacy & Security

### Data Handling
- **No Persistent Storage**: Images processed in memory only
- **Automatic Cleanup**: Temporary files deleted after 1 hour
- **No Logging**: User images never written to logs
- **Memory-Only Processing**: Files never touch persistent storage

### Security Features
- **Rate Limiting**: Configurable request limits
- **File Validation**: Magic byte checking + extension validation
- **Size Limits**: Configurable maximum file size
- **Content Security**: XSS and injection protection
- **HTTPS Only**: SSL termination at proxy level

## 📈 Performance Optimization

### Image Processing
- **Smart Resizing**: Large images resized for processing, then upscaled
- **Memory Management**: Efficient numpy array handling
- **Thread Pool**: Non-blocking background removal
- **Model Caching**: ONNX model loaded once at startup

### System Optimization
- **CPU Targeting**: ONNX runtime configured for CPU execution
- **Memory Limits**: Container resource constraints
- **Cleanup Tasks**: Automatic temporary file removal
- **Health Checks**: Service monitoring and restart

## 🚀 Production Deployment

### 1. Server Setup
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install podman
sudo apt install -y podman podman-compose

# Create service user
sudo useradd -r -s /bin/false clearcut
```

### 2. Deploy Application
```bash
# Clone and deploy
git clone https://github.com/HasanH47/clear-cut.git /opt/clearcut
cd /opt/clearcut
sudo chown -R clearcut:clearcut /opt/clearcut

# Start services
sudo -u clearcut podman-compose up -d
```

### 3. Setup Monitoring
```bash
# Check service status
podman ps
podman logs clearcut

# Monitor resources
podman stats clearcut
```

## 🔧 Troubleshooting

### Common Issues

**Out of Memory Errors**
```bash
# Check memory usage
podman stats clearcut

# Increase swap if needed
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

**Model Loading Fails**
```bash
# Check container logs
podman logs clearcut

# Restart container
podman restart clearcut
```

**Slow Processing**
```bash
# Check CPU usage
htop

# Verify ONNX runtime config
podman exec clearcut python -c "import onnxruntime; print(onnxruntime.get_available_providers())"
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is open-source and available under the MIT License.

## 🌟 Acknowledgments

- **rembg**: Amazing background removal library
- **ONNX Runtime**: High-performance ML inference
- **FastAPI**: Modern Python web framework
- **U²-Net**: Neural network architecture for image segmentation

## 📞 Support

For issues and questions:
- Create an issue on GitHub
- Check the troubleshooting section
- Review container logs for error messages

---

**ClearCut** - Making background removal simple, private, and accessible to everyone! 🎨✂️
