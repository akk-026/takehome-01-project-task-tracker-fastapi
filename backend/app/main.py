from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import parse_qsl, urlencode

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import settings
from app.core.database import initialise_database
from app.core.database import SessionLocal
from app.services.users import seed_demo_users


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialise_database()
    with SessionLocal() as session:
        seed_demo_users(session)
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def restore_vercel_rewrite_path(request: Request, call_next):
    """Restore the original URL after Vercel dispatches to the Python function.

    Vercel's rewrite targets the function file (`/api/index.py`), whereas
    FastAPI needs the browser's original path to match API routes and static
    assets. The rewrite adds the original path as this private query value.
    """
    rewrite_key = "__northstar_path"
    query_items = parse_qsl(request.scope["query_string"].decode(), keep_blank_values=True)
    original_path = next((value for key, value in query_items if key == rewrite_key), None)
    if original_path is not None:
        request.scope["path"] = "/" + original_path.lstrip("/")
        request.scope["raw_path"] = request.scope["path"].encode()
        request.scope["query_string"] = urlencode(
            [(key, value) for key, value in query_items if key != rewrite_key], doseq=True
        ).encode()
    return await call_next(request)


app.include_router(api_router)
frontend_directory = Path(__file__).resolve().parents[2] / "frontend"
app.mount("/", StaticFiles(directory=frontend_directory, html=True), name="frontend")
