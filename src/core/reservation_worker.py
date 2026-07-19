import threading
import time
import queue
from datetime import datetime

from src.notification.discord import send_discord


class ReservationWorker(threading.Thread):
    def __init__(self, manager, trains: list,
                 seat_type: str, window_seat: bool,
                 passengers: dict = None,
                 interval: float = 0.8, discord_webhook: str = "",
                 log_queue: queue.Queue = None,
                 on_success_callback=None, on_status_callback=None):
        super().__init__(daemon=True)
        self.manager = manager
        self.trains = trains
        self.seat_type = seat_type
        self.window_seat = window_seat
        self.passengers = passengers
        self.interval = interval
        self.discord_webhook = discord_webhook
        self.log_queue = log_queue
        self.on_success = on_success_callback
        self.on_status = on_status_callback
        self.stop_event = threading.Event()

    def _log(self, msg: str):
        if self.log_queue is not None:
            ts = datetime.now().strftime("%H:%M:%S")
            self.log_queue.put(f"{ts} {msg}")

    def run(self):
        rail = self.manager.name
        # 이전 실행에서 남은 NetFunnel 키가 만료돼 있으면
        # "Wrong Server ID"로 계속 실패하므로 시작 시 캐시를 비운다
        reset_cache = getattr(self.manager, "reset_netfunnel_cache", None)
        if reset_cache:
            reset_cache()
        send_discord(self.discord_webhook, f"{rail} 예약 매크로를 시작합니다.")
        self._log("예매 시작")
        attempt = 0
        train_count = len(self.trains)
        start_time = time.time()
        last_relogin_time = start_time
        RELOGIN_INTERVAL = 60

        while not self.stop_event.is_set():
            if time.time() - last_relogin_time >= RELOGIN_INTERVAL:
                self._log("세션 유지를 위해 재로그인 중...")
                ok, msg = self.manager.relogin()
                self._log("재로그인 성공" if ok else f"재로그인 실패: {msg}")
                last_relogin_time = time.time()

            idx = attempt % train_count
            train = self.trains[idx]
            attempt += 1
            elapsed = time.time() - start_time
            if self.on_status:
                self.on_status(attempt, elapsed)

            train_name = (f"{rail} {getattr(train, 'train_number', '?')} "
                          f"{getattr(train, 'dep_station_name', '')}"
                          f"→{getattr(train, 'arr_station_name', '')} "
                          f"{getattr(train, 'dep_time', '')}")
            self._log(f"#{attempt} 시도 - {train_name}")

            ok, result = self.manager.reserve(
                train, self.seat_type, self.window_seat, self.passengers)
            if ok:
                reservation = result
                dep_t = getattr(reservation, "dep_time", "")
                arr_t = getattr(reservation, "arr_time", "")
                pay_t = getattr(reservation, "payment_time", "")
                msg = (f"예약 성공! {train_name}\n"
                       f"출발: {dep_t} / 도착: {arr_t}\n"
                       f"결제기한: {pay_t}")
                self._log(msg)
                send_discord(self.discord_webhook, msg)
                if self.on_success:
                    self.on_success(msg)
                return
            else:
                self._log(f"  실패: {result}")

            if self.interval > 0:
                time.sleep(self.interval)

        self._log("예매 중지됨")

    def stop(self):
        self.stop_event.set()
