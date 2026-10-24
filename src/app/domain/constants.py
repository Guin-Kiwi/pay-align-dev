# src/app/domain/constants.py

from datetime import date

# Payroll rules exist for this year only (ADR-002)
RULES_YEAR = 2026
RULES_YEAR_START = date(RULES_YEAR, 1, 1)
RULES_YEAR_END = date(RULES_YEAR, 12, 31)

# Public holidays for Basel-Stadt in RULES_YEAR; the movable ones are valid for that year only
PUBLIC_HOLIDAYS = {
    date(RULES_YEAR, 1, 1),   # New Year's Day
    date(RULES_YEAR, 4, 3),   # Good Friday
    date(RULES_YEAR, 4, 6),   # Easter Monday
    date(RULES_YEAR, 5, 1),   # Labour Day
    date(RULES_YEAR, 5, 14),  # Ascension Day
    date(RULES_YEAR, 5, 25),  # Whit Monday
    date(RULES_YEAR, 8, 1),   # Swiss National Day
    date(RULES_YEAR, 12, 25), # Christmas
    date(RULES_YEAR, 12, 26), # Boxing Day
}

# Social security and tax rates (RULES_YEAR)
AHV_RATE = 0.053  # 5.3%
ALV_RATE = 0.011  # 1.1%
TAX_RATE = 0.05   # 5.0%
NBU_RATE = 0.01432  # 1.432% (applies if weekly hours >= 8)
FAK_RATE = 0.0165  # 1.65%
BU_RATE = 0.00505  # 0.505%
AHV_TOTAL_RATE = AHV_RATE * 2
ADMIN_CHARGE_RATE = 0.05

# Annual limits (RULES_YEAR)
EMPLOYEE_GROSS_LIMIT = 22_680  # CHF 22,680 per employee per employer per year
EMPLOYER_GROSS_LIMIT = 60_480  # CHF 60,480 per employer per year

# Minimum values (RULES_YEAR)
MIN_HOURLY_WAGE = 22.20  # Basel-Stadt cantonal minimum wage for RULES_YEAR (base wage; holiday and 1 August supplements are paid on top). Source: https://www.bs.ch/wsu/awa/arbeitsbeziehungen/loehne/mindestlohn/haeufige-fragen-zum-kantonalen-mindestlohn-faq
MAX_HOURLY_WAGE = 500.00  # Setup ceiling (UC-001): far above any household wage, and keeps the wage in centimes within PostgreSQL's integer column
MIN_WEEKLY_HOURS = 5     # Recommended minimum weekly hours

DAYS_IN_RULES_YEAR = 365

# Holiday entitlement (ADR-004, Amendment 1)
ALLOWED_HOLIDAY_WEEKS = (4, 5)

# NBU applies from 8 weekly hours (ADR-004, Amendment 1)
NBU_MIN_WEEKLY_MINUTES = 8 * 60