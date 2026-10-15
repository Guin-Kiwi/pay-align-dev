def require_fields(**fields: str) -> None:
    for field, value in fields.items():
        if not value or not value.strip():
            label = field.replace("_", " ").capitalize()
            raise ValueError(f"{label} is required.")
