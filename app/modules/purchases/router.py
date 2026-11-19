from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, status

from app.api.dependencies.permissions import require_roles
from app.domains.shared.enums import PurchaseStatus, UserRole
from app.modules.purchases.dependencies import get_purchase_service
from app.modules.purchases.schemas import (
    CheckoutAcceptedResponse,
    CheckoutRequest,
    PurchaseCancellationResponse,
    PurchasePageResponse,
    PurchaseResponse,
)
from app.modules.purchases.service import PurchaseService
from app.modules.users.models import UserModel

router = APIRouter(prefix="/purchases", tags=["Purchases"])
admin_router = APIRouter(prefix="/admin/users", tags=["Admin customer purchases"])


@router.post(
    "/checkout",
    response_model=CheckoutAcceptedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Simular compra de pacote com cartão de crédito",
    description=(
        "A simulação aprova o pagamento automaticamente. Envie um Idempotency-Key único. "
        "Os dados do cartão são descartados e nunca são armazenados."
    ),
)
def checkout(
    data: CheckoutRequest,
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
        min_length=16,
        max_length=128,
        description="UUID ou chave aleatória única por intenção de compra.",
    ),
    current_user: UserModel = Depends(require_roles(UserRole.CLIENT)),
    service: PurchaseService = Depends(get_purchase_service),
) -> CheckoutAcceptedResponse:
    return service.checkout(
        user_id=current_user.id,
        data=data,
        idempotency_key=idempotency_key,
    )


@router.get("/me", response_model=PurchasePageResponse, summary="Listar minhas compras")
def list_my_purchases(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    purchase_status: PurchaseStatus | None = Query(default=None, alias="status"),
    current_user: UserModel = Depends(require_roles(UserRole.CLIENT)),
    service: PurchaseService = Depends(get_purchase_service),
) -> PurchasePageResponse:
    return service.list_my_purchases(
        user_id=current_user.id,
        page=page,
        limit=limit,
        purchase_status=purchase_status,
    )


@router.get("/me/{purchase_id}", response_model=PurchaseResponse, summary="Consultar minha compra")
def get_my_purchase(
    purchase_id: UUID,
    current_user: UserModel = Depends(require_roles(UserRole.CLIENT)),
    service: PurchaseService = Depends(get_purchase_service),
) -> PurchaseResponse:
    return service.get_my_purchase(purchase_id=purchase_id, user_id=current_user.id)


@router.post(
    "/me/{purchase_id}/cancel",
    response_model=PurchaseCancellationResponse,
    summary="Cancelar compra e devolver vagas",
)
def cancel_my_purchase(
    purchase_id: UUID,
    current_user: UserModel = Depends(require_roles(UserRole.CLIENT)),
    service: PurchaseService = Depends(get_purchase_service),
) -> PurchaseCancellationResponse:
    return service.cancel_my_purchase(purchase_id=purchase_id, user_id=current_user.id)


@admin_router.get(
    "/{user_id}/purchases",
    response_model=PurchasePageResponse,
    summary="Consultar compras de um cliente",
)
def list_customer_purchases(
    user_id: UUID,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    purchase_status: PurchaseStatus | None = Query(default=None, alias="status"),
    departure_from: date | None = Query(default=None),
    departure_to: date | None = Query(default=None),
    _current_admin: UserModel = Depends(require_roles(UserRole.ADMIN)),
    service: PurchaseService = Depends(get_purchase_service),
) -> PurchasePageResponse:
    return service.list_customer_purchases(
        customer_id=user_id,
        page=page,
        limit=limit,
        purchase_status=purchase_status,
        departure_from=departure_from,
        departure_to=departure_to,
    )
