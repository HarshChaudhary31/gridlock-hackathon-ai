# Smart Traffic Monitoring & Mobility Intelligence System

**Flipkart Gridlock Hackathon 2.0** — AI-powered CCTV traffic analytics for Bengaluru congestion management.

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green)
![YOLOv8](https://img.shields.io/badge/YOLOv8-Ultralytics-red)
![Streamlit](https://img.shields.io/badge/Dashboard-Streamlit-orange)

## Overview

Production-ready system that analyzes CCTV traffic footage to:

- Detect and count vehicles (cars, bikes, buses, trucks, auto-rickshaws)
- Classify congestion (Low / Medium / Heavy / Gridlock)
- Detect helmet violations and triple riding
- Track vehicles with speed and direction estimation
- Generate heatmaps, alerts, and analytics reports
- Visualize everything on a real-time Streamlit dashboard

## Architecture

```
Video Input → Frame Extraction → YOLOv8 Detection → ByteTrack Tracking
    → Congestion Analysis → Helmet Detection → Analytics Engine
    → Dashboard Visualization → Alerts & Reports
```

## Project Structure

```
traffic-ai/
├── backend/
│   ├── api/routes/       # FastAPI endpoints
│   ├── services/         # AI pipeline & analytics
│   ├── models/           # Pydantic schemas
│   ├── database/         # SQLAlchemy ORM
│   └── utils/
├── frontend/             # Streamlit dashboard
├── uploads/              # Uploaded videos
├── outputs/              # Processed videos & frames
├── reports/              # CSV & summary reports
├── weights/              # Custom YOLO weights (optional)
├── data/sample/          # Sample test videos
├── main.py               # CLI entry point
├── Dockerfile
└── docker-compose.yml
```

## Quick Start

### Prerequisites

- Python 3.11+
- pip
- (Optional) Docker & Docker Compose
- (Optional) CUDA GPU for faster inference

### 1. Clone & Setup

```bash
cd traffic-ai
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

### 2. Run Backend

```bash
export PYTHONPATH=$(pwd)
python main.py backend
```

API available at: **http://localhost:8000**  
Docs: **http://localhost:8000/docs**

### 3. Run Dashboard

```bash
export PYTHONPATH=$(pwd)
python main.py frontend
```

Dashboard: **http://localhost:8501**

### 4. Run Both

```bash
python main.py all
```

## Sample Test Data

Generate and process a synthetic Bengaluru traffic video:

```bash
# Via API
curl -X POST "http://localhost:8000/api/v1/video/sample/generate?duration_sec=10"
curl -X POST "http://localhost:8000/api/v1/video/sample/process?max_frames=150"

# Or use the Streamlit dashboard → Video Processing → Sample Data
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/health` | Health check |
| POST | `/api/v1/video/upload` | Upload & process video |
| POST | `/api/v1/video/process` | Process existing file |
| POST | `/api/v1/video/sample/process` | Process sample video |
| GET | `/api/v1/video/status/{id}` | Processing status |
| GET | `/api/v1/video/frame/{id}` | Latest processed frame |
| GET | `/api/v1/analytics/live/{id}` | Live metrics + forecast |
| GET | `/api/v1/analytics/summary/{id}` | Session summary |
| GET | `/api/v1/reports/traffic/{id}` | Traffic CSV report |
| GET | `/api/v1/reports/violations/{id}` | Violations CSV |

## Docker Deployment

```bash
docker-compose up --build
```

- Backend: http://localhost:8000
- Dashboard: http://localhost:8501

## Configuration

Edit `.env` (from `.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `DEVICE` | `cpu` | `cuda`, `cpu`, or `mps` |
| `YOLO_VEHICLE_MODEL` | `yolov8n.pt` | Vehicle detection weights |
| `CONFIDENCE_THRESHOLD` | `0.35` | Detection confidence |
| `FRAME_SKIP` | `2` | Process every Nth frame |
| `CONGESTION_HEAVY` | `0.75` | Heavy traffic threshold |

### Custom Helmet Model

Place a fine-tuned YOLO helmet model in `weights/` and set:

```
YOLO_HELMET_MODEL=weights/helmet_yolov8.pt
```

## Features Implemented

### Core
- [x] Real-time vehicle detection (YOLOv8)
- [x] Vehicle counting by type
- [x] Congestion classification (4 levels)
- [x] Helmet violation & triple riding detection
- [x] Multi-object tracking (ByteTrack)
- [x] Speed estimation & direction tracking
- [x] Entry/exit counting
- [x] Heatmap visualization
- [x] Accident/anomaly detection
- [x] Alert system with cooldown
- [x] CSV & summary reports
- [x] SQLite analytics database
- [x] Streamlit dark-theme dashboard

### Bonus
- [x] Predictive congestion forecasting
- [x] Dynamic signal timing recommendations
- [x] Emergency vehicle heuristic detection
- [x] Sample video generator for testing

## Scalability Notes

- Use `FRAME_SKIP` to balance speed vs accuracy
- Deploy multiple workers behind a load balancer for API
- Use Redis for session state in multi-instance deployments
- Replace SQLite with PostgreSQL for production
- Use `yolov8s.pt` or `yolov8m.pt` for better accuracy on dense traffic
- GPU (`DEVICE=cuda`) recommended for real-time CCTV

## Hackathon Demo Flow

1. Start backend + frontend
2. Open http://localhost:8501
3. Go to **Video Processing → Sample Data → Generate & Process**
4. Copy the session ID
5. Open **Live Dashboard** — watch real-time metrics, heatmaps, congestion gauge
6. Check **Analytics** and download **Reports**

## License

MIT — Built for Flipkart Gridlock Hackathon 2.0
