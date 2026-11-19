from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.purchases.schemas import CheckoutRequest, CreditCardInput
from app.modules.purchases.service import PurchaseService


def make_checkout(*, package_id=None, quantity=1, number="not-a-real-card"):
    return CheckoutRequest(
        package_id=package_id or uuid4(),
        quantity=quantity,
        card={
            "cardholder_name": "Cliente Teste",
            "card_number": number,
            "expiry_month": "00",
            "expiry_year": "00",
            "cvv": "000",
        },
    )


def test_simulated_card_fields_are_required_but_not_card_validated():
    card = CreditCardInput(
        cardholder_name="Cliente",
        card_number="qualquer-valor",
        expiry_month="00",
        expiry_year="00",
        cvv="x",
    )
    assert card.card_number.get_secret_value() == "qualquer-valor"
    assert "qualquer-valor" not in repr(card)


def test_checkout_rejects_quantity_outside_range():
    with pytest.raises(ValidationError):
        make_checkout(quantity=0)
    with pytest.raises(ValidationError):
        make_checkout(quantity=11)


def test_checkout_rejects_extra_fields():
    payload = make_checkout().model_dump()
    payload["is_admin"] = True
    with pytest.raises(ValidationError):
        CheckoutRequest.model_validate(payload)


def test_idempotency_fingerprint_ignores_card_data():
    package_id = uuid4()
    first = make_checkout(package_id=package_id, quantity=2, number="111")
    retry = make_checkout(package_id=package_id, quantity=2, number="999")
    assert PurchaseService._fingerprint(first) == PurchaseService._fingerprint(retry)


def test_idempotency_fingerprint_changes_when_purchase_intent_changes():
    package_id = uuid4()
    first = make_checkout(package_id=package_id, quantity=1)
    different_quantity = make_checkout(package_id=package_id, quantity=2)
    different_package = make_checkout(package_id=uuid4(), quantity=1)
    assert PurchaseService._fingerprint(first) != PurchaseService._fingerprint(different_quantity)
    assert PurchaseService._fingerprint(first) != PurchaseService._fingerprint(different_package)
