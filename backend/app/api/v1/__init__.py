"""
API v1 routes.
"""

from fastapi import APIRouter
from app.api.v1 import auth, users, grants, evaluations, projects, payments, webhooks, support, slack, contributions

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(grants.router, prefix="/grants", tags=["grants"])
api_router.include_router(evaluations.router, prefix="/evaluations", tags=["evaluations"])
api_router.include_router(payments.router, prefix="/payments", tags=["payments"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
api_router.include_router(support.router, prefix="", tags=["support"])
api_router.include_router(slack.router, prefix="", tags=["slack"])
api_router.include_router(contributions.router, prefix="/contributions", tags=["contributions"])

