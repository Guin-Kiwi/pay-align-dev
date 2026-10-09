# src/app/domain/constants.py

from datetime import date

# Public holidays for Basel-Stadt (2026)
PUBLIC_HOLIDAYS_2026 = {
    date(2026, 1, 1),   # New Year's Day
    date(2026, 1, 2),   # Berchtoldstag
    date(2026, 3, 2),   # Basel Fasnacht (Monday after Ash Wednesday)
    date(2026, 3, 3),   # Basel Fasnacht (Tuesday)
    date(2026, 4, 3),   # Good Friday
    date(2026, 4, 6),   # Easter Monday
    date(2026, 5, 1),   # Labour Day
    date(2026, 5, 14),  # Ascension Day
    date(2026, 5, 25),  # Whit Monday
    date(2026, 8, 1),   # Swiss National Day
    date(2026, 12, 25), # Christmas
    date(2026, 12, 26), # Boxing Day
}

# Social security and tax rates (2026)
AHV_RATE = 0.053  # 5.3%
ALV_RATE = 0.011  # 1.1%
TAX_RATE = 0.05   # 5.0%
NBU_RATE = 0.01432  # 1.432% (applies if weekly hours >= 8)
FAK_RATE = 0.0165  # 1.65%
BU_RATE = 0.00505  # 0.505%
ADMIN_CHARGE_RATE = 0.05  # 5% of employer AHV

# Annual limits (2026)
EMPLOYEE_GROSS_LIMIT = 22_680  # CHF 22,680 per employee per year
EMPLOYER_GROSS_LIMIT = 60_480  # CHF 60,480 per employer per year

# Minimum values (2026)
MIN_HOURLY_WAGE = 23.55  # Basel-Stadt minimum wage (CHF 23.55/hour, effective January 1, 2026). Source: https://www.bs.ch/wsu/awa/arbeitsbeziehungen/loehne/mindestlohn/haeufige-fragen-zum-kantonalen-mindestlohn-faq
MIN_WEEKLY_HOURS = 5     # Recommended minimum weekly hours