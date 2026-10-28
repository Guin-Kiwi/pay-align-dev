import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from src.app.domain import constants
from src.app.interfaces.auth import require_account_id

ASSETS = Path(__file__).resolve().parent / 'static'
NAVIGATION_PLACEHOLDER = '<!-- SHARED_NAVIGATION -->'
HOME_ROUTE = '/home'
BACK_BUTTON = '<button id="back-button" class="back-button" type="button">Back</button>'
ui_router = APIRouter()


def _rules() -> dict:
    return {
        'RULES_YEAR': constants.RULES_YEAR,
        'RULES_YEAR_START': constants.RULES_YEAR_START.isoformat(),
        'RULES_YEAR_END': constants.RULES_YEAR_END.isoformat(),
        'MIN_PASSWORD_LENGTH': constants.MIN_PASSWORD_LENGTH,
        'MIN_HOURLY_WAGE': f'{constants.MIN_HOURLY_WAGE:.2f}',
        'MAX_HOURLY_WAGE': f'{constants.MAX_HOURLY_WAGE:.2f}',
        'ALLOWED_HOLIDAY_WEEKS': list(constants.ALLOWED_HOLIDAY_WEEKS),
    }


def _fill_rules(content: str) -> str:
    rules = _rules()
    for name, value in rules.items():
        if not isinstance(value, list):
            content = content.replace('{{' + name + '}}', str(value))
    options = ''.join(
        f'<option value="{weeks}"{" selected" if index == 0 else ""}>{weeks}</option>'
        for index, weeks in enumerate(rules['ALLOWED_HOLIDAY_WEEKS'])
    )
    return content.replace('{{HOLIDAY_WEEK_OPTIONS}}', options)


@ui_router.get('/setup-assets/constants.js', include_in_schema=False)
def rules_script():
    script = ''.join(f'const {name} = {json.dumps(value)};\n' for name, value in _rules().items())
    return Response(script, media_type='text/javascript', headers={'Cache-Control': 'no-cache'})


class RevalidatedStaticFiles(StaticFiles):
    """Serve the page assets so a browser asks again before reusing a copy; unchanged files answer 304."""

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers['Cache-Control'] = 'no-cache'
        return response


ui_router.mount('/setup-assets', RevalidatedStaticFiles(directory=ASSETS), name='setup-assets')


def _page_with_navigation(page: str, current_route: str) -> HTMLResponse:
    content = (ASSETS / page).read_text(encoding='utf-8')
    navigation = (ASSETS / 'navigation.html').read_text(encoding='utf-8')
    navigation = navigation.replace('{{CURRENT_ROUTE}}', current_route)
    navigation = navigation.replace('{{BACK_BUTTON}}', '' if current_route == HOME_ROUTE else BACK_BUTTON)
    if NAVIGATION_PLACEHOLDER not in content:
        raise RuntimeError(f'{page} is missing the shared navigation placeholder.')
    return HTMLResponse(_fill_rules(content.replace(NAVIGATION_PLACEHOLDER, navigation)))


@ui_router.get('/', include_in_schema=False)
def browser_home():
    return FileResponse(ASSETS / 'welcome.html', media_type='text/html')


@ui_router.get('/login', include_in_schema=False)
def login_page():
    return FileResponse(ASSETS / 'login.html', media_type='text/html')


SIGNED_IN_PAGES = {
    '/home': 'home.html',
    '/timesheets': 'timesheets.html',
    '/employment-setup': 'employment-setup.html',
    '/employees': 'employees.html',
    '/payslips': 'payslips.html',
    '/account-details': 'account-details.html',
}


@ui_router.get('/home', include_in_schema=False)
@ui_router.get('/timesheets', include_in_schema=False)
@ui_router.get('/employment-setup', include_in_schema=False)
@ui_router.get('/employees', include_in_schema=False)
@ui_router.get('/payslips', include_in_schema=False)
@ui_router.get('/account-details', include_in_schema=False)
def signed_in_page(request: Request):
    try:
        account_id = require_account_id(request, request.app.state.account_service)
    except HTTPException as error:
        if error.status_code != 401:
            raise
        return RedirectResponse('/login', status_code=303)
    route = request.url.path
    if route == '/employment-setup' and request.app.state.setup_repository.get_employer(account_id) is None:
        return RedirectResponse('/home', status_code=303)
    return _page_with_navigation(SIGNED_IN_PAGES[route], route)
