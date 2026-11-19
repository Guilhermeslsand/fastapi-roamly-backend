from fastapi import APIRouter

from app.modules.auth.router import router as auth_router
from app.modules.calendar.router import router as calendar_router
from app.modules.dashboard.router import router as dashboard_router
from app.modules.destinations.router import admin_router as admin_destinations_router
from app.modules.destinations.router import router as destinations_router
from app.modules.packages.router import admin_router as admin_packages_router
from app.modules.purchases.router import admin_router as admin_customer_purchases_router
from app.modules.purchases.router import router as purchases_router
from app.modules.packages.router import router as packages_router
from app.modules.users.router import profile_router as users_profile_router
from app.modules.users.router import router as admin_users_router
from app.api.v1.endpoints.health import router as health_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(admin_users_router)
api_router.include_router(users_profile_router)
api_router.include_router(destinations_router)
api_router.include_router(admin_destinations_router)
api_router.include_router(packages_router)
api_router.include_router(admin_packages_router)
api_router.include_router(purchases_router)
api_router.include_router(admin_customer_purchases_router)
api_router.include_router(calendar_router)
api_router.include_router(dashboard_router)