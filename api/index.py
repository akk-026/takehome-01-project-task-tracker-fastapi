"""Vercel entrypoint for the FastAPI application."""

from pathlib import Path
import sys


project_root = Path(__file__).resolve().parents[1]
backend_directory = project_root / "backend"
sys.path.insert(0, str(backend_directory))

from app.main import app  # noqa: E402
