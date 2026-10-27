#!/usr/bin/env python3
"""Fill a local PayAlign with a demo account: one employment up to date, one with months due.

Uses only the app's API, so every saved month passes the normal payroll rules.
Run it against a fresh local database while the app is running:

    python3 scripts/seed_demo.py              # http://localhost:8000
    python3 scripts/seed_demo.py --url http://127.0.0.1:8001
"""

import argparse
import calendar
import json
import sys
from datetime import date
from http.cookiejar import CookieJar
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPCookieProcessor, Request, build_opener

EMAIL = "demo@example.com"
PASSWORD = "demo-pass1"
YEAR = 2026
LOCAL_HOSTS = {"localhost", "127.0.0.1"}

EMPLOYER = {
    "name": "Demo Household",
    "address": "Demoweg 1, 4051 Basel",
    "ahv_number": "756.1111.2222.33",
    "contact_info": EMAIL,
}

UP_TO_DATE = {
    "employee": {
        "name": "Mara Beispiel",
        "address": "Beispielweg 2, 4052 Basel",
        "ahv_number": "756.2222.3333.44",
        "nationality": "CH",
    },
    "employment": {"start_date": "2026-07-01", "hourly_wage": "30.00", "weekly_hours": "6:00", "holiday_weeks": 4},
}

NEEDS_ATTENTION = {
    "employee": {
        "name": "Luca Muster",
        "address": "Musterstrasse 5, 4053 Basel",
        "ahv_number": "756.3333.4444.55",
        "nationality": "IT",
    },
    "employment": {"start_date": "2026-05-04", "hourly_wage": "28.00", "weekly_hours": "4:00", "holiday_weeks": 5},
}


class Client:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip("/")
        self.opener = build_opener(HTTPCookieProcessor(CookieJar()))
        self.csrf_token = None

    def call(self, method, path, body=None):
        headers = {"Content-Type": "application/json"}
        if self.csrf_token:
            headers["X-CSRF-Token"] = self.csrf_token
        data = json.dumps(body).encode() if body is not None else None
        request = Request(self.base_url + path, data=data, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=30) as response:
                return response.status, json.loads(response.read() or b"null")
        except HTTPError as error:
            return error.code, json.loads(error.read() or b"null")


def _days(month, weekdays, start):
    last = calendar.monthrange(YEAR, month)[1]
    return [
        day for day in (date(YEAR, month, number) for number in range(1, last + 1))
        if day.weekday() in weekdays and day >= start
    ]


def _worked(day, start_time, end_time):
    return {"work_date": day.isoformat(), "category": "worked", "start_time": start_time, "end_time": end_time}


def _mara_month(employment_id, month):
    start = date.fromisoformat(UP_TO_DATE["employment"]["start_date"])
    days = _days(month, {1, 3}, start)
    entries = [_worked(day, "09:00", "12:00") for day in days]
    if month == 9:
        entries[0] = {"work_date": days[0].isoformat(), "category": "annual_holiday_taken", "paid_minutes": 180}
    return {
        "employment_id": employment_id,
        "year": YEAR,
        "month": month,
        "cash_bonus": "100.00" if month == 8 else "0.00",
        "expense_reimbursements": "24.50" if month == 10 else "0.00",
        "work_entries": entries,
    }


def _luca_month(employment_id, month):
    start = date.fromisoformat(NEEDS_ATTENTION["employment"]["start_date"])
    entries = []
    for day in _days(month, {0}, start):
        if day == date(YEAR, 5, 25):
            entries.append({"work_date": day.isoformat(), "category": "public_holiday_taken", "paid_minutes": 240})
        else:
            entries.append(_worked(day, "14:00", "18:00"))
    return {"employment_id": employment_id, "year": YEAR, "month": month, "work_entries": entries}


def _require(status, body, expected, step):
    if status != expected:
        raise SystemExit(f"{step} failed ({status}): {body}")
    return body


def _last_month_due(today):
    if today.year > YEAR:
        return 12
    return today.month if today.year == YEAR else 0


def seed(client, today):
    client.csrf_token = _require(*client.call("GET", "/api/v1/auth/csrf"), 200, "CSRF token")["csrf_token"]
    status, body = client.call(
        "POST", "/api/v1/auth/register",
        {"email": EMAIL, "password": PASSWORD, "first_name": "Demo", "last_name": "Employer"},
    )
    if status == 409:
        print(f"The demo account already exists. Log in with {EMAIL} / {PASSWORD}.")
        return
    client.csrf_token = _require(status, body, 201, "Registration")["csrf_token"]
    _require(*client.call("POST", "/api/v1/employer", EMPLOYER), 201, "Employer profile")

    mara = _require(*client.call("POST", "/api/v1/setup", UP_TO_DATE), 201, "Mara's employment")["employment_id"]
    for month in range(7, _last_month_due(today) + 1):
        _require(*client.call("POST", "/api/v1/monthly-payroll", _mara_month(mara, month)), 201, f"Mara {month:02d}/{YEAR}")

    luca = _require(*client.call("POST", "/api/v1/setup", NEEDS_ATTENTION), 201, "Luca's employment")["employment_id"]
    for month in (5, 6):
        _require(*client.call("POST", "/api/v1/monthly-payroll", _luca_month(luca, month)), 201, f"Luca {month:02d}/{YEAR}")

    print(f"Demo data saved. Log in at {client.base_url}/login with {EMAIL} / {PASSWORD}.")
    print("Mara Beispiel is up to date; Luca Muster has months to enter from July.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", default="http://localhost:8000", help="the running app (local only)")
    args = parser.parse_args(argv)
    if urlparse(args.url).hostname not in LOCAL_HOSTS:
        print(f"Refusing to seed {args.url}: demo data is for a local app only.", file=sys.stderr)
        return 2
    try:
        seed(Client(args.url), date.today())
    except URLError as error:
        print(f"Could not reach {args.url}: {error.reason}. Is the app running?", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
