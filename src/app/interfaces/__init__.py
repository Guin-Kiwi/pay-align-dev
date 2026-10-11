from fastapi import FastAPI
from .payroll import payroll_router

app = FastAPI()

app.include_router(payroll_router, prefix="/api/v1")