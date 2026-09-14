<div align="center">

# SmartCleaner

### Intelligent desktop disk-cleaning assistant with a secure backend

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688?logo=fastapi&logoColor=white)
![PyQt6](https://img.shields.io/badge/PyQt6-Desktop-41CD52?logo=qt&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)

</div>

## About

**SmartCleaner** is a client-server application for analyzing disk usage and helping users safely identify files that may be cleaned up.

The project combines a desktop GUI, local filesystem scanning, a REST API, authentication, persistent storage and AI-assisted analysis in a single architecture.

## Highlights

- Desktop interface built with **PyQt6**
- Disk and filesystem analysis using **psutil**
- Safe file removal through **Send2Trash**
- REST backend built with **FastAPI**
- Async persistence with **SQLAlchemy**
- **PostgreSQL** production database support
- JWT-based authentication
- Password hashing with bcrypt/passlib
- Per-IP API rate limiting
- Request-size limits and security headers
- Configurable CORS policy
- Request IDs and structured server logging
- Containerized deployment with **Docker Compose**
- AI-assisted analysis with configurable provider/fallback support
- Automated tests with **pytest**

## Architecture

```text
SmartCleaner
├── client/                  # Desktop application
│   ├── gui/                 # PyQt6 user interface
│   ├── scanner/             # File-system scanning
│   ├── pipeline/            # Analysis pipeline
│   ├── safety/              # Safety checks
│   ├── api_client/          # Backend communication
│   ├── database/            # Client-side persistence helpers
│   └── tests/               # Client tests
│
├── server/                  # FastAPI backend
│   ├── routers/             # API endpoints
│   ├── models/              # Application models
│   ├── database/            # Database layer
│   ├── main.py              # API entry point
│   ├── middleware.py        # Security and request middleware
│   └── docker-compose.yml   # Backend + PostgreSQL stack
│
├── deployment/              # Deployment configuration
└── scripts/                 # Utility / launch scripts
```

## Tech Stack

| Area | Technologies |
|---|---|
| Desktop | Python, PyQt6, psutil, Send2Trash |
| Backend | FastAPI, Uvicorn, Pydantic |
| Database | SQLAlchemy, PostgreSQL, asyncpg, SQLite |
| Security | JWT, bcrypt, passlib, SlowAPI |
| Networking | HTTPX, REST API |
| Infrastructure | Docker, Docker Compose |
| Testing | pytest |

## Backend API

The FastAPI service includes:

- authentication routes;
- analysis endpoints;
- `/health` and `/api/health` health checks;
- request validation;
- rate limiting;
- CORS and security middleware;
- request IDs for easier diagnostics.

Interactive API documentation is available automatically through FastAPI when the backend is running:

```text
http://localhost:8000/docs
```

## Local Setup

### 1. Clone the repository

```bash
git clone https://github.com/VARAGer/project-smart-cleaner-disk.git
cd project-smart-cleaner-disk
```

### 2. Start the backend with Docker

Create your environment configuration from the provided example and set the required secrets.

```bash
cd server
docker compose up --build
```

By default, the API is exposed locally on:

```text
http://127.0.0.1:8000
```

### 3. Run the desktop client

```bash
cd ../client
python -m venv .venv
source .venv/bin/activate   # macOS / Linux
# .venv\Scripts\activate    # Windows
pip install -r requirements.txt
python main.py
```

## Security

The backend includes several defensive controls:

- JWT authentication;
- password hashing;
- rate limiting on sensitive endpoints;
- request body size restrictions;
- security response headers;
- configurable CORS;
- generic validation responses to reduce information leakage;
- local-only default bindings for database/backend services in Docker.

## Project Goal

The goal of SmartCleaner is to demonstrate how a desktop utility can be built as a production-style client-server system rather than as a single local script. The project focuses on clear separation of responsibilities, safe filesystem operations, API security, persistence and deployability.

## Author

**VARAGer**  
GitHub: [@VARAGer](https://github.com/VARAGer)
