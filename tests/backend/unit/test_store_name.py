"""Store rename goes through PATCH /users/me/profile; the schema is the only validation."""
import pytest
from pydantic import ValidationError

from schemas import Schema


def test_store_name_is_trimmed():
    assert Schema.RequestUpdateProfile(store_name="  Rosa Kitchen ").store_name == "Rosa Kitchen"


def test_store_name_optional():
    assert Schema.RequestUpdateProfile(name="Rosa").model_dump(exclude_none=True) == {"name": "Rosa"}


@pytest.mark.parametrize("bad", ["", "   ", "x" * 51])
def test_store_name_rejects_blank_and_too_long(bad):
    with pytest.raises(ValidationError):
        Schema.RequestUpdateProfile(store_name=bad)
