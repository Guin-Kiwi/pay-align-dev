from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from src.app.interfaces.auth import require_account_id

ASSETS = Path(__file__).resolve().parent / 'static'
ui_router = APIRouter()
ui_router.mount('/setup-assets', StaticFiles(directory=ASSETS), name='setup-assets')


@ui_router.get('/setup', include_in_schema=False)
def setup_page(request: Request):
    try:
        require_account_id(request, request.app.state.account_service)
    except HTTPException as error:
        if error.status_code != 401:
            raise
        return RedirectResponse('/login', status_code=303)
    return FileResponse(ASSETS / 'setup.html', media_type='text/html')
