"""SRT/KTX 예약 매크로 웹 백엔드.

기존 데스크톱 앱의 코어(src/core)를 그대로 재사용하고,
GUI 레이어만 REST API로 대체한다. 로컬 단일 사용자 전제라
상태는 프로세스 전역(AppState) 하나로 관리한다.
"""

import os
import queue
import threading

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.config.settings import load_config, save_config
from src.core.korail_manager import KorailManager
from src.core.reservation_worker import ReservationWorker
from src.core.srt_manager import SRTManager

RAILS = {"srt": SRTManager, "ktx": KorailManager}

app = FastAPI(title="srtMacro web")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class DryRunReservation:
    """드라이런 성공 시 워커에 돌려줄 가짜 예약 객체."""

    def __init__(self, train):
        self.dep_time = getattr(train, "dep_time", "")
        self.arr_time = getattr(train, "arr_time", "")
        self.payment_time = "(드라이런 — 실제 예약 아님)"


class DryRunManagerProxy:
    """reserve만 시뮬레이션으로 바꾸고 나머지는 실제 매니저에 위임한다.

    UI/워커 플로우 검증용: 실제 예약 요청이 SRT/코레일 서버로
    절대 나가지 않는다. 처음 몇 번은 매진으로 실패시켜
    재시도 루프까지 눈으로 확인할 수 있게 한다.
    """

    def __init__(self, manager, fail_attempts=4):
        self._m = manager
        self._fails_left = fail_attempts

    def __getattr__(self, name):
        return getattr(self._m, name)

    def reserve(self, train_view, seat_type_str="일반우선",
                window_seat=False, passengers=None):
        if self._fails_left > 0:
            self._fails_left -= 1
            return False, "[드라이런] 좌석 매진 시뮬레이션"
        return True, DryRunReservation(train_view)

    def relogin(self):
        return True, "[드라이런] 재로그인 생략"


class AppState:
    def __init__(self):
        self.rail = None            # "srt" | "ktx"
        self.manager = None
        self.dry_run = os.environ.get(
            "SRTMACRO_DRY_RUN", "").lower() in ("1", "true", "yes")
        self.trains = []            # 마지막 검색 결과 (TrainView)
        self.worker = None
        self.log_queue = queue.Queue()
        self.logs = []              # 로그 누적 버퍼 (폴링용)
        self.lock = threading.Lock()
        self.attempt = 0
        self.elapsed = 0.0
        self.success_message = None

    def drain_logs(self):
        while True:
            try:
                self.logs.append(self.log_queue.get_nowait())
            except queue.Empty:
                break

    def reset_run(self):
        self.attempt = 0
        self.elapsed = 0.0
        self.success_message = None


state = AppState()


def _manager_meta(cls):
    return {
        "name": cls.name,
        "stations": cls.STATIONS,
        "seat_types": cls.SEAT_TYPES,
        "passenger_types": [
            {"label": label, "key": key, "default": default}
            for label, key, default in cls.PASSENGER_TYPES
        ],
        "supports_window_seat": cls.supports_window_seat,
    }


class LoginBody(BaseModel):
    rail: str
    user_id: str
    password: str


class SearchBody(BaseModel):
    dep: str
    arr: str
    date: str          # yyyyMMdd
    time_from: str     # hhmmss


class StartBody(BaseModel):
    train_indices: list[int]
    seat_type: str = "일반우선"
    window_seat: bool = False
    passengers: dict[str, int] = {}
    interval: float = 0.8
    discord_webhook: str = ""


@app.get("/api/meta")
def meta():
    return {rail: _manager_meta(cls) for rail, cls in RAILS.items()}


@app.get("/api/state")
def get_state():
    state.drain_logs()
    running = state.worker is not None and state.worker.is_alive()
    return {
        "rail": state.rail,
        "logged_in": bool(state.manager and state.manager.logged_in),
        "running": running,
        "attempt": state.attempt,
        "elapsed": state.elapsed,
        "success_message": state.success_message,
        "train_count": len(state.trains),
        "dry_run": state.dry_run,
    }


class DryRunBody(BaseModel):
    enabled: bool


@app.post("/api/dryrun")
def set_dry_run(body: DryRunBody):
    if state.worker is not None and state.worker.is_alive():
        raise HTTPException(409, "예매 진행 중에는 변경할 수 없습니다")
    state.dry_run = body.enabled
    return {"dry_run": state.dry_run}


@app.post("/api/login")
def login(body: LoginBody):
    if body.rail not in RAILS:
        raise HTTPException(400, f"unknown rail: {body.rail}")
    if state.worker is not None and state.worker.is_alive():
        raise HTTPException(409, "예매 진행 중에는 로그인할 수 없습니다")
    manager = RAILS[body.rail]()
    ok, msg = manager.login(body.user_id, body.password)
    if not ok:
        raise HTTPException(401, msg)
    state.rail = body.rail
    state.manager = manager
    state.trains = []
    return {"message": msg}


@app.post("/api/logout")
def logout():
    if state.worker is not None and state.worker.is_alive():
        raise HTTPException(409, "예매 진행 중에는 로그아웃할 수 없습니다")
    if state.manager:
        state.manager.logout()
    state.manager = None
    state.rail = None
    state.trains = []
    return {"message": "로그아웃"}


@app.post("/api/search")
def search(body: SearchBody):
    if not state.manager or not state.manager.logged_in:
        raise HTTPException(401, "로그인이 필요합니다")
    ok, result = state.manager.search(
        body.dep, body.arr, body.date, body.time_from)
    if not ok:
        raise HTTPException(502, str(result))
    state.trains = result
    return {
        "trains": [
            {
                "index": i,
                "train_number": t.train_number,
                "dep_station_name": t.dep_station_name,
                "arr_station_name": t.arr_station_name,
                "dep_time": t.dep_time,
                "arr_time": t.arr_time,
                "general_seat_state": t.general_seat_state,
                "special_seat_state": t.special_seat_state,
            }
            for i, t in enumerate(state.trains)
        ]
    }


@app.post("/api/reserve/start")
def reserve_start(body: StartBody):
    if not state.manager or not state.manager.logged_in:
        raise HTTPException(401, "로그인이 필요합니다")
    if state.worker is not None and state.worker.is_alive():
        raise HTTPException(409, "이미 예매가 진행 중입니다")
    try:
        trains = [state.trains[i] for i in body.train_indices]
    except IndexError:
        raise HTTPException(400, "열차 목록이 바뀌었습니다. 다시 검색해주세요")
    if not trains:
        raise HTTPException(400, "예매할 열차를 선택해주세요")

    state.reset_run()
    manager = (DryRunManagerProxy(state.manager)
               if state.dry_run else state.manager)

    def on_status(attempt, elapsed):
        state.attempt = attempt
        state.elapsed = elapsed

    def on_success(msg):
        state.success_message = msg

    state.worker = ReservationWorker(
        manager=manager,
        trains=trains,
        seat_type=body.seat_type,
        window_seat=body.window_seat,
        passengers=body.passengers or None,
        interval=body.interval,
        # 드라이런 중에는 디스코드 알림도 보내지 않는다
        discord_webhook="" if state.dry_run else body.discord_webhook,
        log_queue=state.log_queue,
        on_success_callback=on_success,
        on_status_callback=on_status,
    )
    state.worker.start()
    return {"message": "예매 시작"}


@app.post("/api/reserve/stop")
def reserve_stop():
    if state.worker is not None:
        state.worker.stop()
    return {"message": "중지 요청"}


@app.get("/api/logs")
def get_logs(after: int = 0):
    state.drain_logs()
    return {"logs": state.logs[after:], "next": len(state.logs)}


@app.delete("/api/logs")
def clear_logs():
    state.drain_logs()
    state.logs = []
    return {"message": "cleared"}


@app.get("/api/config/{rail}")
def get_config(rail: str):
    if rail not in RAILS:
        raise HTTPException(400, f"unknown rail: {rail}")
    return load_config(rail)


@app.put("/api/config/{rail}")
def put_config(rail: str, cfg: dict):
    if rail not in RAILS:
        raise HTTPException(400, f"unknown rail: {rail}")
    merged = {**load_config(rail), **cfg}
    save_config(merged, rail)
    return {"message": "saved"}
