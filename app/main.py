from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.fhir_routes import router as fhir_router
from app.api.job_routes import router as job_router
from app.api.payer_routes import router as payer_router
from app.api.preauth_routes import router as preauth_router
from app.api.internal_routes import router as internal_router


app = FastAPI(title="SOM + FHIR Sample", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"ok": True}


app.include_router(fhir_router, prefix="/fhir", tags=["fhir"])
app.include_router(job_router, prefix="/jobs", tags=["jobs"])
app.include_router(payer_router, prefix="/payer", tags=["payer"])
app.include_router(preauth_router, prefix="/preauth", tags=["preauth"])
app.include_router(internal_router, prefix="/internal", tags=["internal"])
