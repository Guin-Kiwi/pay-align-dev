from fastapi import FastAPI

from src.app.interfaces.payroll import payroll_router

app = FastAPI()

app.include_router(payroll_router, prefix="/api/v1")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
