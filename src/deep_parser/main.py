import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from deep_parser.logging_config import configure_logging, logger

from deep_parser.api import upload, retrieve, evaluate, loadtest, jobs, config_api
from deep_parser.webui.routes import router as webui_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    logger.info("Deep Parser API starting up")
    yield
    logger.info("Deep Parser API shutting down")


app = FastAPI(
    title="Deep Parser API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router, prefix="/api")
app.include_router(retrieve.router, prefix="/api")
app.include_router(evaluate.router, prefix="/api")
app.include_router(loadtest.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
app.include_router(config_api.router, prefix="/api")
app.include_router(webui_router, prefix="/ui")

images_dir = Path("images")
images_dir.mkdir(exist_ok=True)
app.mount("/api/images", StaticFiles(directory=str(images_dir)), name="images")


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/")
async def root():
    return {
        "name": "Deep Parser API",
        "version": "1.0.0",
        "description": "RAG content processing system",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
