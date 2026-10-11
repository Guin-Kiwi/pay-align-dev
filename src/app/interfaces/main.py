from fastapi import FastAPI

from src.app.interfaces.payroll import payroll_router

app = FastAPI(title="Payroll Service API", version="1.0.0")
app.include_router(payroll_router)