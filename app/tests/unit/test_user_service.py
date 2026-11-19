from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.domains.shared.enums import UserRole
from app.modules.users.models import UserModel
from app.modules.users.schemas import UserProfileUpdateRequest
from app.modules.users.service import UserService


class FakeDB:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def refresh(self, _entity):
        return None


class FakeUserRepository:
    def __init__(self, _db):
        self.user = UserModel(
            id=uuid4(),
            name="Maria Silva",
            email="maria@example.com",
            cpf="52998224725",
            password_hash="argon2-hash",
            role=UserRole.CLIENT,
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.existing_email = None
        self.existing_cpf = None
        self.customers = []
        self.detail_count = 0
        self.last_list_args = None

    def get_by_id(self, user_id):
        return self.user if self.user.id == user_id else None

    def email_exists(self, email, *, exclude_user_id=None):
        return self.existing_email == email

    def cpf_exists(self, cpf, *, exclude_user_id=None):
        return self.existing_cpf == cpf

    def update(self, user):
        return user

    def list_clients(self, **kwargs):
        self.last_list_args = kwargs
        return self.customers, len(self.customers)

    def get_client_detail(self, user_id):
        return (self.user, self.detail_count) if user_id == self.user.id else None


def build_service(monkeypatch):
    monkeypatch.setattr("app.modules.users.service.UserRepository", FakeUserRepository)
    db = FakeDB()
    service = UserService(db)
    return service, db


def test_update_own_profile_commits_only_sent_fields(monkeypatch):
    service, db = build_service(monkeypatch)
    user = service.update_own_profile(
        user_id=service.users.user.id,
        data=UserProfileUpdateRequest(name="  Maria da Silva  "),
    )
    assert user.name == "Maria da Silva"
    assert user.email == "maria@example.com"
    assert db.commits == 1
    assert db.rollbacks == 0


def test_update_profile_rejects_duplicate_email(monkeypatch):
    service, db = build_service(monkeypatch)
    service.users.existing_email = "other@example.com"
    with pytest.raises(HTTPException) as exc:
        service.update_own_profile(
            user_id=service.users.user.id,
            data=UserProfileUpdateRequest(email="other@example.com"),
        )
    assert exc.value.status_code == 409
    assert db.commits == 0


def test_update_profile_does_not_allow_updating_another_user(monkeypatch):
    service, db = build_service(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        service.update_own_profile(
            user_id=uuid4(),
            data=UserProfileUpdateRequest(name="Outro Nome"),
        )
    assert exc.value.status_code == 404
    assert db.commits == 0


def test_list_customers_returns_pagination_metadata(monkeypatch):
    service, _db = build_service(monkeypatch)
    service.users.customers = [
        UserModel(
            id=uuid4(),
            name="Maria Silva",
            email="maria@example.com",
            cpf="52998224725",
            password_hash="hash",
            role=UserRole.CLIENT,
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
    ]
    result = service.list_customers(page=1, limit=10, search="maria")
    assert result.total == 1
    assert result.pages == 1
    assert result.items[0].email == "maria@example.com"
    assert service.users.last_list_args["search"] == "maria"


def test_customer_detail_includes_purchase_count(monkeypatch):
    service, _db = build_service(monkeypatch)
    service.users.detail_count = 4
    result = service.get_customer(user_id=service.users.user.id)
    assert result.purchases_count == 4
    assert result.name == "Maria Silva"


def test_customer_detail_returns_404_for_non_customer(monkeypatch):
    service, _db = build_service(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        service.get_customer(user_id=uuid4())
    assert exc.value.status_code == 404
