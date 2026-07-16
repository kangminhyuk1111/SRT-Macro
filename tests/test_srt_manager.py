from src.core.srt_manager import SRTManager
from src.core.rail_manager import TrainView, RailManager


class FakeSRTTrain:
    train_number = "301"
    dep_station_name = "동대구"
    arr_station_name = "수서"
    dep_time = "141000"
    arr_time = "151000"
    general_seat_state = "예약가능"
    special_seat_state = "매진"


def test_srt_manager_is_railmanager():
    assert isinstance(SRTManager(), RailManager)


def test_srt_metadata():
    m = SRTManager()
    assert m.name == "SRT"
    assert "수서" in m.STATIONS
    assert m.SEAT_TYPES == ["일반우선", "일반만", "특실우선", "특실만"]
    assert ("어른", "adult", 1) in m.PASSENGER_TYPES
    assert any(key == "disability1to3" for _, key, _ in m.PASSENGER_TYPES)
    assert m.supports_window_seat is True


def test_srt_to_view_normalizes_train():
    m = SRTManager()
    v = m._to_view(FakeSRTTrain())
    assert isinstance(v, TrainView)
    assert v.train_number == "301"
    assert v.dep_station_name == "동대구"
    assert v.general_seat_state == "예약가능"
    assert isinstance(v.raw, FakeSRTTrain)


def test_srt_build_passengers_creates_instances_per_count():
    m = SRTManager()
    plist = m._build_passengers({"adult": 2, "child": 1, "senior": 0,
                                 "disability1to3": 0, "disability4to6": 0})
    assert len(plist) == 3


def test_srt_build_passengers_empty_returns_none():
    m = SRTManager()
    assert m._build_passengers({"adult": 0, "child": 0, "senior": 0,
                                "disability1to3": 0, "disability4to6": 0}) is None
