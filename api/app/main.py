from contextlib import asynccontextmanager

from fastapi import FastAPI

import app.db.models  # noqa: F401 — registers ORM models so Base.metadata is populated
from app.api.routes import router
from app.db.base import Base
from app.db.session import engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(router)
