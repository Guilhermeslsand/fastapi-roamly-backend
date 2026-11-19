import hashlib
import json
import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from math import ceil
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.domains.shared.enums import PaymentMethod, PaymentStatus, PurchaseStatus
from app.modules.purchases.models import PaymentModel, PurchaseModel
from app.modules.purchases.repository import PurchaseRepository
from app.modules.purchases.schemas import (
    CheckoutAcceptedResponse,
    CheckoutRequest,
    PurchaseCancellationResponse,
    PurchasePageResponse,
    PurchaseResponse,
)

logger = logging.getLogger(__name__)


def business_date() -> date:
    """Retorna a data civil no fuso configurado para o negócio."""
    return datetime.now(ZoneInfo(settings.app_timezone)).date()


class PurchaseService:
    """Orquestra checkout, cancelamento e histórico do cliente."""

    def __init__(self, db: Session, cache=None) -> None:
        self.db = db
        self.repository = PurchaseRepository(db)
        self.cache = cache

    @staticmethod
    def _fingerprint(data: CheckoutRequest) -> str:
        # Dados do cartão são deliberadamente excluídos do fingerprint e da persistência.
        payload = {
            "package_id": str(data.package_id),
            "quantity": data.quantity,
            "payment_method": PaymentMethod.CREDIT_CARD.value,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def checkout(
        self,
        *,
        user_id: UUID,
        data: CheckoutRequest,
        idempotency_key: str,
    ) -> CheckoutAcceptedResponse:
        fingerprint = self._fingerprint(data)
        existing = self.repository.get_by_idempotency_key(
            user_id=user_id, idempotency_key=idempotency_key
        )
        if existing is not None:
            return self._replay_or_conflict(existing, fingerprint)

        # O cartão é aceito somente para a simulação. Não persistir, serializar ou logar.
        package = self.repository.get_package_for_update(data.package_id)
        if package is None or not package.is_active:
            raise HTTPException(status_code=404, detail="Pacote não encontrado ou indisponível.")
        if package.departure_date <= business_date():
            raise HTTPException(status_code=409, detail="Não é possível comprar um pacote cuja viagem já começou ou partiu.")
        if package.available_seats < data.quantity:
            raise HTTPException(status_code=409, detail="Não há vagas suficientes para a quantidade solicitada.")

        # Revalida após obter o lock para serializar checkouts concorrentes do mesmo pacote.
        existing = self.repository.get_by_idempotency_key(
            user_id=user_id, idempotency_key=idempotency_key
        )
        if existing is not None:
            return self._replay_or_conflict(existing, fingerprint)

        if self.repository.has_overlapping_confirmed_purchase(
            user_id=user_id,
            departure_date=package.departure_date,
            return_date=package.return_date,
        ):
            raise HTTPException(
                status_code=409,
                detail="Você já possui uma viagem confirmada em datas que se sobrepõem a este pacote.",
            )

        total_amount = (package.price * data.quantity).quantize(Decimal("0.01"))
        cost_amount = (
            (package.cost_price * data.quantity).quantize(Decimal("0.01"))
            if package.cost_price is not None
            else None
        )
        now = datetime.now(timezone.utc)
        purchase_id = uuid4()
        purchase = PurchaseModel(
            id=purchase_id,
            user_id=user_id,
            package_id=package.id,
            quantity=data.quantity,
            total_amount=total_amount,
            cost_amount=cost_amount,
            departure_date=package.departure_date,
            return_date=package.return_date,
            idempotency_key=idempotency_key,
            idempotency_fingerprint=fingerprint,
            status=PurchaseStatus.CONFIRMED,
            purchased_at=now,
        )
        payment = PaymentModel(
            purchase_id=purchase.id,
            amount=total_amount,
            method=PaymentMethod.CREDIT_CARD,
            status=PaymentStatus.APPROVED,
            transaction_reference=f"SIM-{uuid4().hex.upper()}",
            paid_at=now,
        )
        package.available_seats -= data.quantity

        try:
            self.repository.create(purchase, payment)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            sqlstate = getattr(exc.orig, "sqlstate", None) or getattr(exc.orig, "pgcode", None)
            constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
            if sqlstate == "23P01" or constraint == "excl_purchases_user_travel_period":
                raise HTTPException(
                    status_code=409,
                    detail="Você já possui uma viagem confirmada em datas que se sobrepõem a este pacote.",
                ) from exc
            if sqlstate == "23505" or constraint == "uq_purchases_user_idempotency_key":
                replay = self.repository.get_by_idempotency_key(
                    user_id=user_id, idempotency_key=idempotency_key
                )
                if replay is not None:
                    return self._replay_or_conflict(replay, fingerprint)
            raise HTTPException(
                status_code=409,
                detail="Não foi possível concluir a compra devido a um conflito de integridade.",
            ) from exc

        self._invalidate_package_cache()
        created = self.repository.get_for_user(purchase_id=purchase.id, user_id=user_id)
        if created is None:
            raise HTTPException(status_code=500, detail="Compra criada, mas não foi possível consultá-la.")
        return CheckoutAcceptedResponse.model_validate(created)

    def list_my_purchases(
        self,
        *,
        user_id: UUID,
        page: int,
        limit: int,
        purchase_status: PurchaseStatus | None,
    ) -> PurchasePageResponse:
        items, total = self.repository.list_for_user(
            user_id=user_id, page=page, limit=limit, status=purchase_status
        )
        return PurchasePageResponse(
            items=[PurchaseResponse.model_validate(item) for item in items],
            total=total,
            page=page,
            limit=limit,
            pages=ceil(total / limit) if total else 0,
        )

    def get_my_purchase(self, *, purchase_id: UUID, user_id: UUID) -> PurchaseResponse:
        purchase = self.repository.get_for_user(purchase_id=purchase_id, user_id=user_id)
        if purchase is None:
            # Não revela se o ID existe para outro usuário.
            raise HTTPException(status_code=404, detail="Compra não encontrada.")
        return PurchaseResponse.model_validate(purchase)

    def cancel_my_purchase(
        self, *, purchase_id: UUID, user_id: UUID
    ) -> PurchaseCancellationResponse:
        reference = self.repository.get_reference_for_user(
            purchase_id=purchase_id, user_id=user_id
        )
        if reference is None:
            raise HTTPException(status_code=404, detail="Compra não encontrada.")

        # Mantém a mesma ordem de locks do checkout: pacote antes da compra.
        package = self.repository.get_package_for_update(reference.package_id)
        purchase = self.repository.get_for_user_for_update(
            purchase_id=purchase_id, user_id=user_id
        )
        if purchase is None:
            raise HTTPException(status_code=404, detail="Compra não encontrada.")
        if package is None:
            raise HTTPException(status_code=409, detail="Pacote associado à compra não encontrado.")
        if purchase.status != PurchaseStatus.CONFIRMED:
            raise HTTPException(
                status_code=409,
                detail="Somente compras confirmadas podem ser canceladas.",
            )
        if purchase.departure_date <= business_date():
            raise HTTPException(
                status_code=409,
                detail="Não é possível cancelar uma viagem que já começou ou cuja partida é hoje.",
            )
        if purchase.payment is None or purchase.payment.status != PaymentStatus.APPROVED:
            raise HTTPException(status_code=409, detail="Pagamento da compra não está em estado cancelável.")

        purchase.status = PurchaseStatus.CANCELLED
        purchase.payment.status = PaymentStatus.REFUNDED
        package.available_seats += purchase.quantity
        if package.available_seats > package.total_seats:
            self.db.rollback()
            raise HTTPException(
                status_code=409,
                detail="Não foi possível devolver as vagas devido à capacidade atual do pacote.",
            )
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(status_code=409, detail="Não foi possível cancelar a compra.") from exc

        self._invalidate_package_cache()
        cancelled = self.repository.get_for_user(purchase_id=purchase_id, user_id=user_id)
        if cancelled is None:
            raise HTTPException(status_code=500, detail="Compra cancelada, mas não foi possível consultá-la.")
        return PurchaseCancellationResponse.model_validate(cancelled)

    @staticmethod
    def _replay_or_conflict(
        existing: PurchaseModel, fingerprint: str
    ) -> CheckoutAcceptedResponse:
        if existing.idempotency_fingerprint != fingerprint:
            raise HTTPException(
                status_code=409,
                detail="A chave de idempotência já foi utilizada com dados de compra diferentes.",
            )
        return CheckoutAcceptedResponse.model_validate(existing)

    def _invalidate_package_cache(self) -> None:
        if self.cache is None:
            return
        try:
            self.cache.invalidate_prefix("packages")
        except Exception:
            # A compra/cancelamento já foi confirmada no PostgreSQL; cache é best-effort.
            logger.warning("Falha ao invalidar cache de pacotes após operação de compra", exc_info=True)

