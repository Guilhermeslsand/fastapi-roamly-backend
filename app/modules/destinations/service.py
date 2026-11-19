import logging
from math import ceil
from uuid import UUID

from fastapi import HTTPException
from redis.exceptions import RedisError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from pydantic import ValidationError

from app.core.config import settings
from app.modules.destinations.models import DestinationModel
from app.modules.destinations.repository import DestinationRepository
from app.modules.destinations.schemas import (
    DestinationCreateRequest,
    DestinationPageResponse,
    DestinationResponse,
    DestinationUpdateRequest,
)
from app.redis.cache import RedisCache

logger = logging.getLogger(__name__)


class DestinationService:
    def __init__(self, db: Session, cache: RedisCache) -> None:
        self.db = db
        self.repository = DestinationRepository(db)
        self.cache = cache

    def list_public(
        self, *, page: int, limit: int, q: str | None, country: str | None,
        state: str | None, sort_order: str,
    ) -> DestinationPageResponse:
        params = {
            "page": page, "limit": limit, "q": q, "country": country,
            "state": state, "sort_order": sort_order, "is_active": True,
        }
        key = self.cache.build_key("destinations:list", params)
        try:
            cached = self.cache.get_json(key)
            if cached is not None:
                return DestinationPageResponse.model_validate(cached)
        except (RedisError, ValidationError, ValueError):
            logger.warning("Falha ao consultar cache de destinos", exc_info=True)

        items, total = self.repository.list_destinations(
            page=page, limit=limit, q=q, country=country, state=state,
            is_active=True, sort_order=sort_order,
        )
        response = DestinationPageResponse(
            items=[DestinationResponse.model_validate(item) for item in items],
            total=total,
            page=page,
            limit=limit,
            pages=ceil(total / limit) if total else 0,
        )
        try:
            self.cache.set_json(
                key, response.model_dump(mode="json"), settings.destinations_cache_ttl_seconds
            )
        except RedisError:
            logger.warning("Falha ao gravar cache de destinos", exc_info=True)
        return response

    def list_admin(
        self, *, page: int, limit: int, q: str | None, country: str | None,
        state: str | None, is_active: bool | None, sort_order: str,
    ) -> DestinationPageResponse:
        items, total = self.repository.list_destinations(
            page=page, limit=limit, q=q, country=country, state=state,
            is_active=is_active, sort_order=sort_order,
        )
        return DestinationPageResponse(
            items=[DestinationResponse.model_validate(item) for item in items],
            total=total,
            page=page,
            limit=limit,
            pages=ceil(total / limit) if total else 0,
        )

    def get_public(self, destination_id: UUID) -> DestinationResponse:
        key = self.cache.build_key("destinations:item", {"id": str(destination_id)})
        try:
            cached = self.cache.get_json(key)
            if cached is not None:
                return DestinationResponse.model_validate(cached)
        except (RedisError, ValidationError, ValueError):
            logger.warning("Falha ao consultar cache de destino", exc_info=True)

        destination = self.repository.get_by_id(destination_id)
        if destination is None or not destination.is_active:
            raise HTTPException(status_code=404, detail="Destino não encontrado.")
        response = DestinationResponse.model_validate(destination)
        try:
            self.cache.set_json(
                key, response.model_dump(mode="json"), settings.destinations_cache_ttl_seconds
            )
        except RedisError:
            logger.warning("Falha ao gravar cache de destino", exc_info=True)
        return response

    def get_admin(self, destination_id: UUID) -> DestinationResponse:
        destination = self.repository.get_by_id(destination_id)
        if destination is None:
            raise HTTPException(status_code=404, detail="Destino não encontrado.")
        return DestinationResponse.model_validate(destination)

    def create(self, data: DestinationCreateRequest) -> DestinationResponse:
        if self.repository.find_duplicate(
            name=data.name, country=data.country, state=data.state
        ):
            raise HTTPException(status_code=409, detail="Este destino já está cadastrado.")

        destination = DestinationModel(**data.model_dump())
        try:
            self.repository.create(destination)
            self.db.commit()
            self.db.refresh(destination)
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(status_code=409, detail="Destino já cadastrado ou inválido.") from exc

        self._invalidate_cache()
        return DestinationResponse.model_validate(destination)

    def update(
        self, destination_id: UUID, data: DestinationUpdateRequest
    ) -> DestinationResponse:
        destination = self.repository.get_by_id(destination_id)
        if destination is None:
            raise HTTPException(status_code=404, detail="Destino não encontrado.")

        changes = data.model_dump(exclude_unset=True)
        if changes.get("is_active") is False and destination.is_active:
            if self.repository.has_active_packages(destination_id):
                raise HTTPException(
                    status_code=409,
                    detail="Desative os pacotes associados antes de desativar este destino.",
                )

        name = changes.get("name", destination.name)
        country = changes.get("country", destination.country)
        state = changes.get("state", destination.state)
        if self.repository.find_duplicate(
            name=name, country=country, state=state, exclude_id=destination_id
        ):
            raise HTTPException(status_code=409, detail="Já existe um destino com esses dados.")

        for field_name, value in changes.items():
            setattr(destination, field_name, value)

        try:
            self.db.commit()
            self.db.refresh(destination)
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(status_code=409, detail="Não foi possível atualizar o destino.") from exc

        self._invalidate_cache()
        return DestinationResponse.model_validate(destination)

    def deactivate(self, destination_id: UUID) -> None:
        destination = self.repository.get_by_id(destination_id)
        if destination is None:
            raise HTTPException(status_code=404, detail="Destino não encontrado.")
        if self.repository.has_active_packages(destination_id):
            raise HTTPException(
                status_code=409,
                detail="Desative os pacotes associados antes de desativar este destino.",
            )
        destination.is_active = False
        self.db.commit()
        self._invalidate_cache()

    def _invalidate_cache(self) -> None:
        for namespace in ("destinations", "packages"):
            try:
                self.cache.invalidate_prefix(namespace)
            except RedisError:
                # A gravação no PostgreSQL já foi confirmada; cache expirará pelo TTL.
                logger.warning("Falha ao invalidar cache %s", namespace, exc_info=True)
