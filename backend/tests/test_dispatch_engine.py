from app.services.dispatch_engine import (
    CallRequest,
    CarState,
    congestion_by_floor,
    congestion_split_by_floor,
    pick_car,
    score_car,
)


def test_reject_when_full():
    car = CarState(1, 5, "idle", load=8, capacity=8)
    call = CallRequest(1, 5, "up", passengers=1)
    r = score_car(car, call)
    assert r.accepted is False
    assert "满员" in r.reason


def test_same_direction_beats_far_idle():
    cars = [
        CarState(1, 2, "up", load=1, capacity=10),
        CarState(2, 12, "idle", load=0, capacity=10),
    ]
    call = CallRequest(9, 4, "up", 1)
    best = pick_car(cars, call)
    assert best is not None
    assert best.car_id == 1


def test_closer_idle_wins_when_opposite():
    cars = [
        CarState(1, 10, "down", load=0, capacity=10),
        CarState(2, 3, "idle", load=0, capacity=10),
    ]
    call = CallRequest(3, 2, "up", 1)
    best = pick_car(cars, call)
    assert best is not None
    assert best.car_id == 2


# —— congestion: waiting / assigned split ——

def test_congestion_by_floor_counts_only_waiting():
    # 现网口径：waiting-only；assigned / rejected 一律不计
    calls = [
        CallRequest(1, 5, "up", 2, "waiting"),
        CallRequest(2, 5, "up", 1, "assigned"),
        CallRequest(3, 9, "down", 3, "rejected"),
    ]
    assert congestion_by_floor(calls) == {5: 2}


def test_split_separates_waiting_and_assigned_per_floor():
    calls = [
        CallRequest(1, 5, "up", 2, "waiting"),
        CallRequest(2, 5, "up", 3, "waiting"),
        CallRequest(3, 5, "down", 4, "assigned"),
        CallRequest(4, 9, "up", 1, "assigned"),
        CallRequest(5, 9, "up", 2, "rejected"),  # 不计入任一列
    ]
    split = congestion_split_by_floor(calls)
    assert split[5].waiting == 5
    assert split[5].assigned == 4
    assert split[5].total == 9
    assert split[9].waiting == 0
    assert split[9].assigned == 1
    assert split[9].total == 1


def test_split_waiting_column_matches_legacy_count():
    # 新接口 waiting 列必须与现网 congestion_by_floor 完全一致
    calls = [
        CallRequest(1, 3, "up", 1, "waiting"),
        CallRequest(2, 3, "up", 2, "assigned"),
        CallRequest(3, 7, "down", 3, "waiting"),
    ]
    split = congestion_split_by_floor(calls)
    legacy = congestion_by_floor(calls)
    by_floor = {f: s.waiting for f, s in split.items()}
    assert by_floor == legacy
