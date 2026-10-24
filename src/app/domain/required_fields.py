def require_fields(**fields: str) -> None:
    for field, value in fields.items():
        label = field.replace("_", " ").capitalize()
        if not value or not value.strip():
            raise ValueError(f"{label} is required.")
        if "\x00" in value:
            raise ValueError(f"{label} must not contain a NUL character.")
