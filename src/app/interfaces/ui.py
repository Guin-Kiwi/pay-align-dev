from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from src.app.interfaces.auth import require_account_id

ASSETS = Path(__file__).resolve().parent / 'static'
ui_router = APIRouter()
ui_router.mount('/setup-assets', StaticFiles(directory=ASSETS), name='setup-assets')


@ui_router.get('/', include_in_schema=False)
def browser_home():
    return RedirectResponse('/login', status_code=303)


@ui_router.get('/login', include_in_schema=False)
def login_page():
    return FileResponse(ASSETS / 'login.html', media_type='text/html')


@ui_router.get('/setup', include_in_schema=False)
def setup_page(request: Request):
    try:
        require_account_id(request, request.app.state.account_service)
    except HTTPException as error:
        if error.status_code != 401:
            raise
        return RedirectResponse('/login', status_code=303)
    return FileResponse(ASSETS / 'setup.html', media_type='text/html')


@ui_router.get('/payslips', include_in_schema=False)
def payslips_page(request: Request):
    try:
        require_account_id(request, request.app.state.account_service)
    except HTTPException as error:
        if error.status_code != 401:
            raise
        return RedirectResponse('/login', status_code=303)
    return FileResponse(ASSETS / 'payslip.html', media_type='text/html')


@ui_router.get('/employments', include_in_schema=False)
def employments_page(request: Request):
    try:
        require_account_id(request, request.app.state.account_service)
    except HTTPException as error:
        if error.status_code != 401:
            raise
        return RedirectResponse('/login', status_code=303)
    return FileResponse(ASSETS / 'employments.html', media_type='text/html')
