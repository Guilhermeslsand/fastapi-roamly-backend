from fastapi import APIRouter
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.home import router as home_router
from app.modules.auth.router import router as auth_router
from app.modules.users.routers.admin_router import router as admin_router

api_router = APIRouter()
api_router.include_router(home_router)
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(admin_router)

