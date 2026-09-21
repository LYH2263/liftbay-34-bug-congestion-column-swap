"""Elevator dispatch: same-direction preference + floor distance; reject if car full."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CarState:
    car_id: int
    floor: int
    direction: str  # "up" | "down" | "idle"
    load: int
    capacity: int


@dataclass(frozen=True)
class CallRequest:
    call_id: int
    floor: int
    direction: str  # desired travel after boarding
    passengers: int = 1
    # "waiting"（候梯中）| "assigned"（派工成功、尚未取消或清客）
    # 其余状态（rejected 等）不参与拥堵统计
    status: str = "waiting"


@dataclass(frozen=True)
class FloorCongestion:
    floor: int
    waiting: int = 0
    assigned: int = 0

    @property
    def total(self) -> int:
        return self.waiting + self.assigned


@dataclass(frozen=True)
class ScoreResult:
    car_id: int
    score: float
    accepted: bool
    reason: str


SAME_DIR_BONUS = 40.0
IDLE_BONUS = 20.0
DISTANCE_WEIGHT = 5.0


def score_car(car: CarState, call: CallRequest) -> ScoreResult:
    if car.load + call.passengers > car.capacity:
        return ScoreResult(car.car_id, -1e9, False, "轿厢满员")

    distance = abs(car.floor - call.floor)
    score = 100.0 - distance * DISTANCE_WEIGHT

    if car.direction == "idle":
        score += IDLE_BONUS
    elif car.direction == call.direction:
        # approaching or already going same way
        if car.direction == "up" and car.floor <= call.floor:
            score += SAME_DIR_BONUS
        elif car.direction == "down" and car.floor >= call.floor:
            score += SAME_DIR_BONUS
        else:
            score -= 15.0  # same dir but already passed
    else:
        score -= 25.0

    return ScoreResult(car.car_id, score, True, "ok")


def pick_car(cars: list[CarState], call: CallRequest) -> ScoreResult | None:
    results = [score_car(c, call) for c in cars]
    accepted = [r for r in results if r.accepted]
    if not accepted:
        return None
    return max(accepted, key=lambda r: r.score)


def congestion_by_floor(calls: list[CallRequest]) -> dict[int, int]:
    """现网口径：仅统计 waiting 呼梯的候梯人数（按候梯层）。"""
    counts: dict[int, int] = {}
    for c in calls:
        if c.status != "waiting":
            continue
        counts[c.floor] = counts.get(c.floor, 0) + c.passengers
    return counts


def congestion_split_by_floor(calls: list[CallRequest]) -> dict[int, FloorCongestion]:
    """按候梯层拆分两列：
    - waiting：候梯中的人数（与 congestion_by_floor 同口径）
    - assigned：派工成功、尚未取消或清客前，仍占用候梯层的人数
    rejected 等其他状态不计入任一列。
    """
    floors: dict[int, FloorCongestion] = {}
    for c in calls:
        cur = floors.get(c.floor, FloorCongestion(floor=c.floor))
        if c.status == "waiting":
            floors[c.floor] = FloorCongestion(
                c.floor, cur.waiting + c.passengers, cur.assigned
            )
        elif c.status == "assigned":
            floors[c.floor] = FloorCongestion(
                c.floor, cur.waiting, cur.assigned + c.passengers
            )
    return floors
