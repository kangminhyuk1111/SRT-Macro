from src.core.rail_manager import TrainView, RailManager


def test_trainview_holds_normalized_fields_and_raw():
    raw = object()
    v = TrainView(
        train_number="301",
        dep_station_name="동대구",
        arr_station_name="수서",
        dep_time="141000",
        arr_time="151000",
        general_seat_state="예약가능",
        special_seat_state="매진",
        raw=raw,
    )
    assert v.train_number == "301"
    assert v.dep_station_name == "동대구"
    assert v.arr_station_name == "수서"
    assert v.dep_time == "141000"
    assert v.arr_time == "151000"
    assert v.general_seat_state == "예약가능"
    assert v.special_seat_state == "매진"
    assert v.raw is raw


def test_railmanager_base_declares_metadata_attrs():
    m = RailManager()
    assert m.name == ""
    assert m.STATIONS == []
    assert m.SEAT_TYPES == []
    assert m.PASSENGER_TYPES == []
    assert m.supports_window_seat is False


def test_railmanager_methods_raise_not_implemented():
    m = RailManager()
    import pytest
    with pytest.raises(NotImplementedError):
        m.login("a", "b")
    with pytest.raises(NotImplementedError):
        m.search("동대구", "수서", "20260525", "140000")
