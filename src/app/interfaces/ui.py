from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

ASSETS = Path(__file__).resolve().parent / 'static'
ui_router = APIRouter()
ui_router.mount('/setup-assets', StaticFiles(directory=ASSETS), name='setup-assets')


@ui_router.get('/setup', include_in_schema=False)
def setup_page():
    return FileResponse(ASSETS / 'setup.html', media_type='text/html')
