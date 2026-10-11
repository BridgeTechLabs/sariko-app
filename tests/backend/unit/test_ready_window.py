"""Scheduled orders may only be marked ready 45 min before delivery_appointment
(marking ready books Lalamove immediately)."""
from datetime import datetime, timezone

from apis.sellers import ready_opens_at


def test_no_appointment_is_always_open():
    assert ready_opens_at({"delivery_appointment": None}) is None
    assert ready_opens_at({}) is None


def test_opens_45_minutes_before_appointment():
    # Postgres timestamptz as PostgREST returns it
    opens = ready_opens_at({"delivery_appointment": "2026-10-12T12:00:00+07:00"})
    assert opens == datetime(2026, 10, 12, 4, 15, tzinfo=timezone.utc)
