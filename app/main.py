import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import SQLModel

# Charger les modèles avant SQLModel.metadata.create_all()
from . import models
from .database import engine
from .routers import (
    auth,
    matching,
    cnps,
    jobs,
    applications,
    profile,
    favorites,
    messages,
    interviews,
    notifications,
    alerts,
    admin,
    support,
    reviews,
    career,
    assessments,
    referrals,
    portfolio,
    billing,
    reports,
    network,
)

app = FastAPI(
    title="EmploiCamer API",
    description="Backend de l'application EmploiCamer / AfriJob Connect",
    version="0.1.0",
)

# CORS_ORIGINS accepts a comma-separated list of allowed browser origins.
cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "*").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)

app.include_router(auth.router)
app.include_router(matching.router)
app.include_router(cnps.router)
app.include_router(jobs.router)
app.include_router(applications.router)
app.include_router(profile.router)
app.include_router(favorites.router)
app.include_router(messages.router)
app.include_router(interviews.router)
app.include_router(notifications.router)
app.include_router(alerts.router)
app.include_router(admin.router)
app.include_router(support.router)
app.include_router(reviews.router)
app.include_router(career.router)
app.include_router(assessments.router)
app.include_router(referrals.router)
app.include_router(portfolio.router)
app.include_router(billing.router)
app.include_router(reports.router)
app.include_router(network.router)


@app.on_event("startup") 
def on_startup():
    """Create SQLModel tables if they do not exist yet."""
    SQLModel.metadata.create_all(engine)


@app.get("/")
def health_check():
    return {"status": "ok", "message": "EmploiCamer API en ligne"}


@app.get("/version")
def get_version():
    return {"version": "0.1.0"}
