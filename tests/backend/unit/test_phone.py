"""Phone normalization on PATCH /users/me/profile.

Why this matters: the stored phone is what Lalamove gets at booking time. A bad
number accepted at onboarding only fails later, on the seller's "ready" click.
"""
import pytest
from fastapi import HTTPException


@pytest.mark.parametrize("raw", ["0901234567", "901234567", "84901234567", "+84 901 234 567", "090-123-4567"])
def test_vn_formats_normalize_to_e164(raw):
    from core.phone import to_e164_vn

    assert to_e164_vn(raw) == "+84901234567"


@pytest.mark.parametrize("raw", ["", "abc", "12345678", "0123456789012", "+82 10-1234-5678", "00901234567"])
def test_invalid_phone_rejected(raw):
    from core.phone import to_e164_vn

    with pytest.raises(ValueError):
        to_e164_vn(raw)


def test_update_profile_refuses_invalid_phone_with_422():
    """Rejected before any DAO call — nothing is written."""
    from apis.users import update_current_user_profile
    from schemas import Schema

    with pytest.raises(HTTPException) as exc:
        update_current_user_profile(Schema.RequestUpdateProfile(phone="abc"), user={"id": "u1"})

    assert exc.value.status_code == 422
    # ButtonGroup.vue matches on this exact string to stay on the page.
    assert exc.value.detail == "Invalid phone number"
