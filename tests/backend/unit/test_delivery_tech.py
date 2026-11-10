"""T180 (docs/dev/20261110-delivery-tech): the current trip of an order lists (A26), the "no driver since" clock (A36),
the trip fee (A12). No DB."""
from types import SimpleNamespace

from apis import deliveries
from dao.dao_orders import with_current_trip
from services.allingo_service import trip_fields


def test_a26c_lists_read_the_newest_trip():
    order = {"deliveries": [{"status": "CANCELED", "created_at": "2026-11-10T03:00:00"},
                            {"status": "ON_GOING", "created_at": "2026-11-10T04:00:00"},
                            {"status": "EXPIRED", "created_at": "2026-11-10T01:00:00"}]}
    assert with_current_trip(order)["delivery_status"] == "ON_GOING"
    assert with_current_trip({"deliveries": []})["delivery_status"] is None


def test_a36a_status_since_is_the_start_of_the_current_status():
    h = [{"status": "ASSIGNING_DRIVER", "changed_at": "t1"}, {"status": "ON_GOING", "changed_at": "t2"},
         {"status": "ASSIGNING_DRIVER", "changed_at": "t3"}, {"status": "ASSIGNING_DRIVER", "changed_at": "t4"}]
    assert deliveries.status_since(h, "ASSIGNING_DRIVER") == "t3"   # a driver turned it down at t3
    assert deliveries.status_since([], "ASSIGNING_DRIVER") is None   # trips before the history trigger


def test_a12a_allingo_trip_fee_in_whole_dong():
    trip = {"id": "ord_1", "delivery": {"status": "queued"}, "fee": {"cod": 0, "total": "34800.00"}}
    assert trip_fields(trip)["trip_fee"] == 34800 and type(trip_fields(trip)["trip_fee"]) is int
    assert trip_fields({"id": "ord_1", "delivery": {}})["trip_fee"] is None   # no fee in the answer: not invented
