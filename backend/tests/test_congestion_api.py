from collections import defaultdict

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.models import Building, CallTicket, ElevatorCar


@pytest.fixture()
def ctx():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False)

    def _get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_db

    # 造数：5F 两张 waiting（2+3 人）、9F 一张 assigned（1 人）、12F 一张 rejected（4 人）
    db = Session()
    b = Building(name="测试楼", floors=18)
    db.add(b)
    db.flush()
    car = ElevatorCar(building_id=b.id, label="T1", floor=1,
                      direction="idle", load=0, capacity=10)
    db.add(car)
    db.flush()
    db.add_all([
        CallTicket(building_id=b.id, floor=5, direction="up", passengers=2,
                   status="waiting"),
        CallTicket(building_id=b.id, floor=5, direction="up", passengers=3,
                   status="waiting"),
        CallTicket(building_id=b.id, floor=9, direction="down", passengers=1,
                   status="assigned", assigned_car_id=car.id, score="80.0"),
        CallTicket(building_id=b.id, floor=12, direction="up", passengers=4,
                   status="rejected"),
    ])
    db.commit()
    db.close()

    # 不用 with：不触发 lifespan（避免连 Postgres / 自动 seed）
    client = TestClient(app)
    yield client, Session
    app.dependency_overrides.clear()


def _congestion_map(client):
    return {r["floor"]: r for r in client.get("/api/congestion").json()}


def _calls_chain(client):
    """以呼梯列表为唯一事实源，按 (楼层, 状态) 汇总人数。"""
    calls = client.get("/api/calls").json()
    chain: dict[tuple[int, str], int] = defaultdict(int)
    floors = set()
    for c in calls:
        if c["status"] in ("waiting", "assigned"):
            chain[(c["floor"], c["status"])] += c["passengers"]
            floors.add(c["floor"])
    return calls, chain, floors


def _assert_matches_chain(client):
    calls, chain, floors = _calls_chain(client)
    rows = client.get("/api/congestion").json()
    assert {r["floor"] for r in rows} == floors
    for r in rows:
        assert r["waiting"] == chain[(r["floor"], "waiting")]
        assert r["assigned"] == chain[(r["floor"], "assigned")]
        assert r["total"] == r["waiting"] + r["assigned"]
    active = [c for c in calls if c["status"] in ("waiting", "assigned")]
    assert sum(r["total"] for r in rows) == sum(c["passengers"] for c in active)
    assert sum(r["waiting"] for r in rows) == sum(
        c["passengers"] for c in calls if c["status"] == "waiting"
    )
    assert sum(r["assigned"] for r in rows) == sum(
        c["passengers"] for c in calls if c["status"] == "assigned"
    )
    return calls, rows


def test_two_columns_initial(ctx):
    client, _ = ctx
    m = _congestion_map(client)
    # 5F：waiting 5；9F：assigned 1；12F rejected 不出现
    assert set(m) == {5, 9}
    assert m[5] == {"floor": 5, "waiting": 5, "assigned": 0, "total": 5}
    assert m[9] == {"floor": 9, "waiting": 0, "assigned": 1, "total": 1}
    # 按 total 降序，同量按楼层
    assert [r["floor"] for r in client.get("/api/congestion").json()] == [5, 9]


def test_matches_calls_chain_before_dispatch(ctx):
    client, _ = ctx
    _assert_matches_chain(client)


def test_columns_move_on_dispatch_and_total_conserved(ctx):
    client, _ = ctx
    call_id = next(
        c["id"] for c in client.get("/api/calls").json()
        if c["floor"] == 5 and c["status"] == "waiting" and c["passengers"] == 2
    )
    before = _congestion_map(client)[5]

    r = client.post("/api/dispatch", json={"call_id": call_id})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "assigned" and body["assigned_car_id"] is not None

    after = _congestion_map(client)[5]
    # 派工成功：waiting 降 2、assigned 升 2、合计不变
    assert after["waiting"] == before["waiting"] - 2
    assert after["assigned"] == before["assigned"] + 2
    assert after["total"] == before["total"] == 5


def test_matches_calls_chain_after_dispatch(ctx):
    client, _ = ctx
    call_id = next(
        c["id"] for c in client.get("/api/calls").json()
        if c["floor"] == 5 and c["status"] == "waiting"
    )
    assert client.post("/api/dispatch", json={"call_id": call_id}).status_code == 200
    _assert_matches_chain(client)


def test_rejected_dispatch_counted_in_neither_column(ctx):
    client, Session = ctx
    # 占满轿厢：再派任何 waiting 票都会 409 rejected
    db = Session()
    car = db.scalars(select(ElevatorCar)).one()
    car.load = car.capacity
    db.commit()
    db.close()

    # /calls 按 id 降序，这里显式锁定 2 人票：它 rejected 后 5F 应剩另一张 3 人票
    target = next(
        c for c in client.get("/api/calls").json()
        if c["floor"] == 5 and c["status"] == "waiting" and c["passengers"] == 2
    )
    r = client.post("/api/dispatch", json={"call_id": target["id"]})
    assert r.status_code == 409

    # 票据已 rejected：不计入任一列；5F 只剩另一张 3 人 waiting 票
    m = _congestion_map(client)
    assert m[5]["waiting"] == 3
    assert m[5]["assigned"] == 0
    assert m[5]["total"] == 3
    # 数字链依旧对齐
    _assert_matches_chain(client)
