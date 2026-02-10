"""WebUI routes serving Jinja2 templates."""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["webui"])

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@router.get("/", response_class=HTMLResponse)
async def upload_page(request: Request):
    """Render the upload page (home)."""
    return templates.TemplateResponse("upload.html", {"request": request, "active_page": "upload"})


@router.get("/jobs", response_class=HTMLResponse)
async def jobs_page(request: Request):
    """Render the jobs management page."""
    return templates.TemplateResponse("jobs.html", {"request": request, "active_page": "jobs"})


@router.get("/config", response_class=HTMLResponse)
async def config_page(request: Request):
    """Render the configuration page."""
    return templates.TemplateResponse("config.html", {"request": request, "active_page": "config"})


@router.get("/search", response_class=HTMLResponse)
async def search_page(request: Request):
    """Render the search/retrieval debug page."""
    return templates.TemplateResponse("search.html", {"request": request, "active_page": "search"})


@router.get("/evaluate", response_class=HTMLResponse)
async def evaluate_page(request: Request):
    """Render the RAGAS evaluation page."""
    return templates.TemplateResponse("evaluate.html", {"request": request, "active_page": "evaluate"})


@router.get("/loadtest", response_class=HTMLResponse)
async def loadtest_page(request: Request):
    """Render the load testing page."""
    return templates.TemplateResponse("loadtest.html", {"request": request, "active_page": "loadtest"})
