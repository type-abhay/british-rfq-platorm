"""
App entrypoint. Table creation via create_all() here is for quick
local dev only — in a real deployment, Alembic migrations (not
create_all) are the source of truth for schema, so the same change
can be applied consistently across dev/staging/prod.
"""
from fastapi import FastAPI

from app.database import Base, engine
from app.routers import bids, rfqs

app = FastAPI(title="British Auction RFQ System")

app.include_router(rfqs.router)
app.include_router(bids.router)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health():
    return {"status": "ok"}
