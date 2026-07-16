import queue
import time
from src.core.reservation_worker import ReservationWorker
from src.core.rail_manager import TrainView


class FakeManager:
    name = "KTX"

    def __init__(self, succeed_on=1):
        self.calls = 0
        self.succeed_on = succeed_on

    def relogin(self):
        return True, "ok"

    def reserve(self, train_view, seat_type, window_seat, passengers):
        self.calls += 1
        if self.calls >= self.succeed_on:
            class R:
                dep_time = "110000"
                arr_time = "134200"
                payment_time = "20260525120000"
            return True, R()
        return False, "매진"


def _train():
    return TrainView("101", "서울", "부산", "110000", "134200",
                     "예약가능", "매진", raw=object())


def test_worker_reports_status_and_succeeds():
    statuses = []
    q = queue.Queue()
    w = ReservationWorker(
        manager=FakeManager(succeed_on=2),
        trains=[_train()],
        seat_type="일반우선", window_seat=False, passengers=None,
        interval=0.0, discord_webhook="", log_queue=q,
        on_success_callback=lambda msg: None,
        on_status_callback=lambda a, e: statuses.append((a, e)),
    )
    w.start()
    w.join(timeout=5)
    assert not w.is_alive()
    assert len(statuses) >= 1
    logs = []
    while not q.empty():
        logs.append(q.get())
    assert any("KTX" in line for line in logs)


def test_worker_stop_sets_flag():
    w = ReservationWorker(
        manager=FakeManager(succeed_on=999),
        trains=[_train()],
        seat_type="일반우선", window_seat=False, passengers=None,
        interval=10.0, discord_webhook="", log_queue=queue.Queue(),
    )
    w.stop()
    assert w.stop_event.is_set()
