import re

AHV_NUMBER_FORMAT = "756.XXXX.XXXX.XX"
_AHV_NUMBER = re.compile(r"756\.[0-9]{4}\.[0-9]{4}\.[0-9]{2}")


def validate_ahv_number(ahv_number: str) -> None:
    if not ahv_number:
        raise ValueError("AHV number is required.")
    if not _AHV_NUMBER.fullmatch(ahv_number):
        raise ValueError(f"Invalid AHV number format. Use {AHV_NUMBER_FORMAT}.")
