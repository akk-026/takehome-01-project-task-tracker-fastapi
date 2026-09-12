from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
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
app.include_router(api_router)
frontend_directory = Path(__file__).resolve().parents[2] / "frontend"
app.mount("/", StaticFiles(directory=frontend_directory, html=True), name="frontend")
