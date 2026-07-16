from src.core.korail_manager import KorailManager
from src.core.rail_manager import TrainView, RailManager


def test_korail_login_patches_stale_version(monkeypatch):
    """korail2가 검색/예약에 쓰는 self._version 이 2019년 값이라 코레일이 거부한다.
    로그인 직후 매니저가 최신 버전으로 덮어써야 한다."""
    import korail2

    class FakeKorail:
        _version = "190617001"  # 라이브러리 기본값(구버전)

        def __init__(self, korail_id, korail_pw, auto_login=True):
            self.korail_id = korail_id

    monkeypatch.setattr(korail2, "Korail", FakeKorail)
    m = KorailManager()
    ok, msg = m.login("id", "pw")
    assert ok
    assert m._korail._version == KorailManager.KORAIL_VERSION
    assert KorailManager.KORAIL_VERSION != "190617001"


class FakeKorailTrain:
    train_no = "101"
    dep_name = "서울"
    arr_name = "부산"
    dep_time = "110000"
    arr_time = "134200"

    def __init__(self, gen=True, spe=False):
        self._gen = gen
        self._spe = spe

    def has_general_seat(self):
        return self._gen

    def has_special_seat(self):
        return self._spe


def test_korail_manager_is_railmanager():
    assert isinstance(KorailManager(), RailManager)


def test_korail_metadata():
    m = KorailManager()
    assert m.name == "KTX"
    assert "서울" in m.STATIONS
    assert "부산" in m.STATIONS
    assert m.supports_window_seat is False
    keys = [key for _, key, _ in m.PASSENGER_TYPES]
    assert "toddler" in keys
    assert "disability1to3" not in keys


def test_korail_to_view_normalizes_seat_state():
    m = KorailManager()
    v = m._to_view(FakeKorailTrain(gen=True, spe=False))
    assert isinstance(v, TrainView)
    assert v.train_number == "101"
    assert v.dep_station_name == "서울"
    assert v.general_seat_state == "예약가능"
    assert v.special_seat_state == "매진"
    assert isinstance(v.raw, FakeKorailTrain)


def test_korail_build_passengers_uses_count_arguments():
    m = KorailManager()
    plist = m._build_passengers({"adult": 2, "child": 0, "senior": 1, "toddler": 0})
    assert len(plist) == 2
    counts = sorted(p.count for p in plist)
    assert counts == [1, 2]


def test_korail_build_passengers_empty_returns_none():
    m = KorailManager()
    assert m._build_passengers({"adult": 0, "child": 0, "senior": 0, "toddler": 0}) is None


def test_korail_seat_option_mapping():
    m = KorailManager()
    from korail2 import ReserveOption
    assert m._seat_option("일반만") == ReserveOption.GENERAL_ONLY
    assert m._seat_option("특실우선") == ReserveOption.SPECIAL_FIRST
    assert m._seat_option("없는값") == ReserveOption.GENERAL_FIRST
