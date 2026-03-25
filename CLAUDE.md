# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**MediaScan Toolbox** is a Flask-based web app for scanning video libraries to identify files using optimized codecs (HEVC/AV1) versus those needing transcoding. It supports hardware-accelerated transcoding via NVENC and real-time job progress via Server-Sent Events.

**External dependency**: FFmpeg with ffprobe must be installed on the system.

## Running the App

```bash
./run.sh          # Sets up venv, installs deps, starts Flask on http://localhost:5000
```

Or manually:
```bash
pip install -r requirements.txt
python app.py
```

No lint or test suite exists in this project.

## Architecture

The entire app lives in two files:

- **`app.py`** — Flask backend (~533 lines): all business logic, API routes, job management
- **`templates/index.html`** — Single-page frontend (~2003 lines): HTML/CSS/JS, no framework

### Backend Structure (`app.py`)

| Layer | Lines | Responsibility |
|-------|-------|----------------|
| Helpers | 18–41 | `format_size()`, `format_bitrate()`, `res_label_from()` |
| Probe | 43–116 | `probe_file()` — calls ffprobe, extracts codec/resolution/audio metadata |
| Scan | 118–133 | `scan_directory()` — recursive video file discovery |
| Jobs | 135–200 | Background ffmpeg thread management with UUID job IDs, thread-safe `jobs` dict |
| Routes | 201–531 | Flask API endpoints (see below) |

### API Routes

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | Serve frontend |
| GET | `/api/browse` | Directory navigation |
| POST | `/api/scan` | Scan a directory, return file list + stats |
| POST | `/api/probe` | Probe a single file with ffprobe |
| GET | `/api/caps` | Detect available GPU encoders (NVENC) |
| POST | `/api/edit/audio` | Remove/keep audio tracks (stream copy) |
| POST | `/api/transcode` | Transcode video (HEVC or AV1, CPU or GPU) |
| GET | `/api/job/<id>/stream` | SSE stream for real-time job progress |
| POST | `/api/job/<id>/cancel` | Kill a running ffmpeg job |

### Key Design Decisions

- **Job system**: ffmpeg runs in a background thread; UUID job ID returned immediately; frontend polls via SSE (`/api/job/<id>/stream`)
- **Thread safety**: global `jobs` dict protected by `threading.Lock`
- **Output files**: named `original.hevc.mkv` / `original.av1.nvenc.mkv`, auto-incremented if the name already exists
- **Stream mapping**: smart filtering excludes unsupported subtitle formats and attachment streams to prevent ffmpeg failures
- **GPU detection**: NVENC availability checked once at startup via `detect_nvenc()`; uses constQP mode (QP, not CRF) for GPU encodes
- **"Optimized" definition**: a file is considered optimized if its video codec is HEVC or AV1
