from fastapi import APIRouter
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.home import router as home_router
from app.modules.auth.router import router as auth_router
from app.modules.destinations.router import admin_router as admin_destinations_router
from app.modules.destinations.router import router as destinations_router
from app.modules.packages.router import admin_router as admin_packages_router
from app.modules.packages.router import router as packages_router
from app.modules.users.router import router as admin_users_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(admin_users_router)
api_router.include_router(destinations_router)
api_router.include_router(admin_destinations_router)
api_router.include_router(packages_router)
api_router.include_router(admin_packages_router)

