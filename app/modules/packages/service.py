import logging
from math import ceil
from uuid import UUID

from fastapi import HTTPException
from pydantic import ValidationError
from redis.exceptions import RedisError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.packages.models import TravelPackageModel
from app.modules.packages.repository import PackageRepository
from app.modules.packages.schemas import (
    PackageAdminPageResponse,
    PackageAdminResponse,
    PackageAdminSearchParams,
    PackageCreateRequest,
    PackagePageResponse,
    PackageResponse,
    PackageSearchParams,
    PackageUpdateRequest,
)
from app.redis.cache import RedisCache

logger = logging.getLogger(__name__)


class PackageService:
    def __init__(self, db: Session, cache: RedisCache) -> None:
        self.db = db
        self.repository = PackageRepository(db)
        self.cache = cache

    def search_public(self, params: PackageSearchParams) -> PackagePageResponse:
        cache_params = params.model_dump(exclude_none=True, mode="json")
        key = self.cache.build_key("packages:list", cache_params)
        try:
            cached = self.cache.get_json(key)
            if cached is not None:
                return PackagePageResponse.model_validate(cached)
        except (RedisError, ValidationError, ValueError):
            logger.warning("Falha ao consultar cache de pacotes", exc_info=True)

        items, total = self.repository.search(params, public_only=True)
        response = PackagePageResponse(
            items=[PackageResponse.model_validate(item) for item in items],
            total=total,
            page=params.page,
            limit=params.limit,
            pages=ceil(total / params.limit) if total else 0,
        )
        try:
            self.cache.set_json(
                key, response.model_dump(mode="json"), settings.packages_cache_ttl_seconds
            )
        except RedisError:
            logger.warning("Falha ao gravar cache de pacotes", exc_info=True)
        return response

    def search_admin(self, params: PackageAdminSearchParams) -> PackageAdminPageResponse:
        items, total = self.repository.search(params, public_only=False)
        return PackageAdminPageResponse(
            items=[PackageAdminResponse.model_validate(item) for item in items],
            total=total,
            page=params.page,
            limit=params.limit,
            pages=ceil(total / params.limit) if total else 0,
        )

    def get_public(self, package_id: UUID) -> PackageResponse:
        key = self.cache.build_key("packages:item", {"id": str(package_id)})
        try:
            cached = self.cache.get_json(key)
            if cached is not None:
                return PackageResponse.model_validate(cached)
        except (RedisError, ValidationError, ValueError):
            logger.warning("Falha ao consultar cache de pacote", exc_info=True)

        package = self.repository.get_public_by_id(package_id)
        if package is None:
            raise HTTPException(status_code=404, detail="Pacote não encontrado.")
        response = PackageResponse.model_validate(package)
        try:
            self.cache.set_json(
                key, response.model_dump(mode="json"), settings.packages_cache_ttl_seconds
            )
        except RedisError:
            logger.warning("Falha ao gravar cache de pacote", exc_info=True)
        return response

    def get_admin(self, package_id: UUID) -> PackageAdminResponse:
        package = self.repository.get_by_id(package_id)
        if package is None:
            raise HTTPException(status_code=404, detail="Pacote não encontrado.")
        return PackageAdminResponse.model_validate(package)

    def create(self, data: PackageCreateRequest, *, admin_id: UUID) -> PackageAdminResponse:
        if not self.repository.active_destinations_exist(
            {data.origin_id, data.destination_id}
        ):
            raise HTTPException(
                status_code=422,
                detail="Origem e destino devem existir e estar ativos.",
            )

        package = TravelPackageModel(
            **data.model_dump(),
            available_seats=data.total_seats,
            created_by=admin_id,
        )
        try:
            self.repository.create(package)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=409,
                detail="Não foi possível criar o pacote. Verifique os destinos e os dados informados.",
            ) from exc

        self._invalidate_cache()
        created = self.repository.get_by_id(package.id)
        if created is None:
            raise HTTPException(status_code=500, detail="Pacote criado, mas não foi possível consultá-lo.")
        return PackageAdminResponse.model_validate(created)

    def update(
        self, package_id: UUID, data: PackageUpdateRequest
    ) -> PackageAdminResponse:
        package = self.repository.get_by_id(package_id)
        if package is None:
            raise HTTPException(status_code=404, detail="Pacote não encontrado.")

        changes = data.model_dump(exclude_unset=True)
        origin_id = changes.get("origin_id", package.origin_id)
        destination_id = changes.get("destination_id", package.destination_id)
        if origin_id == destination_id:
            raise HTTPException(status_code=422, detail="Origem e destino devem ser diferentes.")
        if not self.repository.active_destinations_exist({origin_id, destination_id}):
            raise HTTPException(
                status_code=422,
                detail="Origem e destino devem existir e estar ativos.",
            )

        trip_fields = {"origin_id", "destination_id", "departure_date", "return_date"}
        if trip_fields.intersection(changes) and self.repository.has_purchases(package_id):
            raise HTTPException(
                status_code=409,
                detail=(
                    "Não é permitido alterar origem, destino ou período de um pacote "
                    "que já possui compras. Crie um novo pacote para outro itinerário."
                ),
            )

        departure_date = changes.get("departure_date", package.departure_date)
        return_date = changes.get("return_date", package.return_date)
        if departure_date >= return_date:
            raise HTTPException(
                status_code=422,
                detail="A data de retorno deve ser posterior à data de partida.",
            )

        if "total_seats" in changes:
            already_sold_or_reserved = package.total_seats - package.available_seats
            new_total = changes["total_seats"]
            if new_total < already_sold_or_reserved:
                raise HTTPException(
                    status_code=409,
                    detail="O total de vagas não pode ser menor que a quantidade já vendida ou reservada.",
                )
            package.available_seats = new_total - already_sold_or_reserved
            package.total_seats = new_total
            changes.pop("total_seats")

        for field_name, value in changes.items():
            setattr(package, field_name, value)

        try:
            self.repository.flush()
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=409,
                detail="Não foi possível atualizar o pacote devido a uma restrição de integridade.",
            ) from exc

        self._invalidate_cache()
        updated = self.repository.get_by_id(package_id)
        if updated is None:
            raise HTTPException(status_code=404, detail="Pacote não encontrado.")
        return PackageAdminResponse.model_validate(updated)

    def deactivate(self, package_id: UUID) -> None:
        package = self.repository.get_by_id(package_id)
        if package is None:
            raise HTTPException(status_code=404, detail="Pacote não encontrado.")
        package.is_active = False
        self.db.commit()
        self._invalidate_cache()

    def _invalidate_cache(self) -> None:
        try:
            self.cache.invalidate_prefix("packages")
        except RedisError:
            # O TTL limita a duração de dados antigos caso Redis esteja indisponível.
            logger.warning("Falha ao invalidar cache de pacotes", exc_info=True)
