# KTX 지원 추가 + GUI 현대화 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** SRT 전용 예약 매크로에 KTX(코레일) 예약을 추가하고, 시작 시 SRT/KTX를 고르는 런처와 현대적 GUI 테마(sv-ttk)를 입힌다.

**Architecture:** `RailManager` 추상 베이스 아래 `SRTManager`/`KorailManager` 두 구현을 두고, 두 매니저의 `search()`가 라이브러리 열차를 공통 `TrainView`로 정규화한다. GUI 프레임은 매니저 메타데이터(역/좌석/승객/창가석 지원)로 구동되어 한 벌만 유지한다. `main.py`는 런처를 띄우고, 고른 철도의 매니저로 `App`을 만든다.

**Tech Stack:** Python 3.11, tkinter/ttk, sv-ttk(테마), SRT 라이브러리, korail2, pytest(테스트)

참조 설계: `docs/superpowers/specs/2026-06-21-ktx-support-design.md`

실행 환경: 이 프로젝트는 venv `venv311`을 쓴다. 모든 python/pytest/pip 명령은 `venv311/bin/...`로 실행한다. 이 디렉터리는 git 저장소가 아니므로 커밋 단계는 건너뛴다(각 Task 끝에서 `git` 단계가 있으면 무시).

---

## File Structure

| 파일 | 책임 |
|---|---|
| `src/core/rail_manager.py` | **신규** — `RailManager` 베이스 + `TrainView` 정규화 클래스 |
| `src/core/srt_manager.py` | 기존 → `RailManager` 구현. 메타데이터 노출, `search()`가 `TrainView` 반환, lazy import |
| `src/core/korail_manager.py` | **신규** — `KorailManager` 구현 |
| `src/config/settings.py` | 철도별 설정 파일(`config.srt.json`/`config.ktx.json`) 지원 |
| `src/core/reservation_worker.py` | 철도 비종속화(`manager.name`), 시도/경과 상태 보고 |
| `src/gui/search_frame.py` | 역/좌석/승객/창가석을 매니저 메타데이터로 구동, 스왑·날짜 버튼 |
| `src/gui/train_list_frame.py` | 전체선택/해제, 좌석상태 색상 태그 |
| `src/gui/reserve_frame.py` | 시도 횟수·경과 시간 카운터 |
| `src/gui/login_frame.py` | 회원번호/비밀번호 찾기 링크 철도별 |
| `src/gui/app.py` | `manager` 주입, sv-ttk 테마, 제목 동적 |
| `src/gui/launcher.py` | **신규** — SRT/KTX 선택 창 |
| `main.py` | 런처 호출 |
| `requirements.txt` | korail2, sv-ttk 추가 |
| `tests/` | **신규** — 단위 테스트 |

---

## Task 1: 의존성 추가

**Files:**
- Modify: `requirements.txt`
- 설치: venv311

- [ ] **Step 1: requirements.txt 갱신**

`requirements.txt` 전체를 다음으로 교체:

```
SRTrain
requests
korail2
sv-ttk
```

- [ ] **Step 2: 의존성 + 테스트 도구 설치**

Run:
```bash
venv311/bin/pip install korail2 sv-ttk pytest
```
Expected: `Successfully installed ...` (korail2, sv-ttk는 이미 설치돼 있을 수 있음 → "already satisfied" 정상)

- [ ] **Step 3: import 스모크 확인**

Run:
```bash
venv311/bin/python -c "import korail2, sv_ttk, pytest, SRT; print('deps OK')"
```
Expected: `deps OK`

---

## Task 2: RailManager 베이스 + TrainView

**Files:**
- Create: `src/core/rail_manager.py`
- Test: `tests/test_rail_manager.py`
- Create: `tests/__init__.py` (빈 파일)

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/__init__.py`를 빈 파일로 생성. 그리고 `tests/test_rail_manager.py`:

```python
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
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `venv311/bin/python -m pytest tests/test_rail_manager.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'src.core.rail_manager'`)

- [ ] **Step 3: 구현 작성**

`src/core/rail_manager.py`:

```python
class TrainView:
    """SRT/KTX 열차를 GUI/워커가 읽는 통일된 형태로 정규화한 어댑터.

    raw 에는 원본 라이브러리 열차 객체가 들어가며, 예약 시 매니저가 이를 사용한다.
    """

    def __init__(self, train_number, dep_station_name, arr_station_name,
                 dep_time, arr_time, general_seat_state, special_seat_state, raw):
        self.train_number = train_number
        self.dep_station_name = dep_station_name
        self.arr_station_name = arr_station_name
        self.dep_time = dep_time
        self.arr_time = arr_time
        self.general_seat_state = general_seat_state
        self.special_seat_state = special_seat_state
        self.raw = raw


class RailManager:
    """철도(SRT/KTX) 공통 인터페이스. 구현체가 메타데이터와 메서드를 채운다."""

    name = ""
    STATIONS = []
    SEAT_TYPES = []
    PASSENGER_TYPES = []        # [(label, key, default), ...]
    supports_window_seat = False
    find_id_url = ""
    find_pw_url = ""

    @property
    def logged_in(self) -> bool:
        return False

    def login(self, user_id: str, password: str):
        raise NotImplementedError

    def search(self, dep, arr, date, time_from, passengers=None):
        raise NotImplementedError

    def reserve(self, train_view, seat_type_str="일반우선",
                window_seat=False, passengers=None):
        raise NotImplementedError

    def relogin(self):
        raise NotImplementedError

    def logout(self):
        raise NotImplementedError
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `venv311/bin/python -m pytest tests/test_rail_manager.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: 커밋** (git 저장소 아님 → 건너뜀)

---

## Task 3: SRTManager 를 RailManager 구현으로 리팩터링

**Files:**
- Modify: `src/core/srt_manager.py`
- Test: `tests/test_srt_manager.py`

기존 동작(SRT 검색/예약)을 유지하되, `search()`가 `TrainView`를 반환하고, 메타데이터를 노출하고, `from SRT import ...`를 메서드 내부 lazy import로 옮긴다. `STATIONS` 상수는 다른 코드가 import할 수 있으니 모듈 레벨에 그대로 둔다.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_srt_manager.py`:

```python
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
    # 어른 2 + 어린이 1 = 3개 인스턴스
    assert len(plist) == 3


def test_srt_build_passengers_empty_returns_none():
    m = SRTManager()
    assert m._build_passengers({"adult": 0, "child": 0, "senior": 0,
                                "disability1to3": 0, "disability4to6": 0}) is None
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `venv311/bin/python -m pytest tests/test_srt_manager.py -v`
Expected: FAIL (`isinstance ... RailManager` False, `_to_view` 없음 등)

- [ ] **Step 3: 구현 작성**

`src/core/srt_manager.py` 전체를 다음으로 교체:

```python
from src.core.rail_manager import RailManager, TrainView

STATIONS = [
    "수서", "동탄", "평택지제", "천안아산", "오송", "대전",
    "김천구미", "서대구", "동대구", "신경주", "울산(통도사)",
    "부산", "공주", "익산", "정읍", "광주송정", "나주", "목포",
]

SEAT_TYPES = ["일반우선", "일반만", "특실우선", "특실만"]

PASSENGER_TYPES = [
    ("어른", "adult", 1),
    ("어린이", "child", 0),
    ("경로", "senior", 0),
    ("장애1~3", "disability1to3", 0),
    ("장애4~6", "disability4to6", 0),
]


class SRTManager(RailManager):
    name = "SRT"
    STATIONS = STATIONS
    SEAT_TYPES = SEAT_TYPES
    PASSENGER_TYPES = PASSENGER_TYPES
    supports_window_seat = True
    find_id_url = "https://etk.srail.kr/cmc/01/selectCfrmInfo.do?pageId=TK0703000000"
    find_pw_url = "https://etk.srail.kr/cmc/01/selectUserForm.do?pageId=TK0704000000"

    def __init__(self):
        self._srt = None
        self._id = None
        self._pw = None

    @property
    def logged_in(self) -> bool:
        return self._srt is not None

    def login(self, srt_id: str, password: str):
        try:
            from SRT import SRT
            self._srt = SRT(srt_id, password)
            self._id = srt_id
            self._pw = password
            return True, "로그인 성공"
        except Exception as e:
            self._srt = None
            return False, str(e)

    def _to_view(self, t) -> TrainView:
        return TrainView(
            train_number=getattr(t, "train_number", ""),
            dep_station_name=getattr(t, "dep_station_name", ""),
            arr_station_name=getattr(t, "arr_station_name", ""),
            dep_time=getattr(t, "dep_time", ""),
            arr_time=getattr(t, "arr_time", ""),
            general_seat_state=getattr(t, "general_seat_state", ""),
            special_seat_state=getattr(t, "special_seat_state", ""),
            raw=t,
        )

    def search(self, dep, arr, date, time_from, passengers=None):
        if not self._srt:
            return False, "로그인이 필요합니다"
        try:
            trains = self._srt.search_train(
                dep, arr, date, time_from, available_only=False,
            )
            return True, [self._to_view(t) for t in trains]
        except Exception as e:
            return False, str(e)

    def _build_passengers(self, passengers: dict):
        if not passengers:
            return None
        from SRT.passenger import (Adult, Child, Senior,
                                   Disability1To3, Disability4To6)
        plist = []
        for _ in range(passengers.get("adult", 1)):
            plist.append(Adult())
        for _ in range(passengers.get("child", 0)):
            plist.append(Child())
        for _ in range(passengers.get("senior", 0)):
            plist.append(Senior())
        for _ in range(passengers.get("disability1to3", 0)):
            plist.append(Disability1To3())
        for _ in range(passengers.get("disability4to6", 0)):
            plist.append(Disability4To6())
        return plist if plist else None

    def _seat_type(self, seat_type_str: str):
        from SRT import SeatType
        mapping = {
            "일반우선": SeatType.GENERAL_FIRST,
            "일반만": SeatType.GENERAL_ONLY,
            "특실우선": SeatType.SPECIAL_FIRST,
            "특실만": SeatType.SPECIAL_ONLY,
        }
        return mapping.get(seat_type_str, SeatType.GENERAL_FIRST)

    def reserve(self, train_view, seat_type_str="일반우선",
                window_seat=False, passengers=None):
        if not self._srt:
            return False, "로그인이 필요합니다"
        from SRT.errors import SRTNotLoggedInError
        train = getattr(train_view, "raw", train_view)
        seat_type = self._seat_type(seat_type_str)
        kwargs = {"special_seat": seat_type}
        if window_seat:
            kwargs["window_seat"] = True
        plist = self._build_passengers(passengers)
        if plist:
            kwargs["passengers"] = plist
        try:
            reservation = self._srt.reserve(train, **kwargs)
            return True, reservation
        except SRTNotLoggedInError:
            ok, msg = self.login(self._id, self._pw)
            if ok:
                try:
                    reservation = self._srt.reserve(train, **kwargs)
                    return True, reservation
                except Exception as e2:
                    return False, str(e2)
            return False, f"재로그인 실패: {msg}"
        except Exception as e:
            return False, str(e)

    def relogin(self):
        if not self._id or not self._pw:
            return False, "저장된 로그인 정보가 없습니다"
        self._srt = None
        return self.login(self._id, self._pw)

    def logout(self):
        if self._srt:
            try:
                self._srt.logout()
            except Exception:
                pass
            self._srt = None
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `venv311/bin/python -m pytest tests/test_srt_manager.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: 워커 호환 회귀 확인** (이 시점엔 worker가 아직 train.attr 직접 접근. 다음 Task에서 정리)

Run: `venv311/bin/python -c "from src.core.srt_manager import SRTManager, STATIONS; print(len(STATIONS))"`
Expected: `18`

---

## Task 4: KorailManager 구현

**Files:**
- Create: `src/core/korail_manager.py`
- Test: `tests/test_korail_manager.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_korail_manager.py`:

```python
from src.core.korail_manager import KorailManager
from src.core.rail_manager import TrainView, RailManager


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
    # KTX 는 장애 승객 없음, 유아 있음
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
    # 어른(2), 경로(1) → 2개의 Passenger 객체(개수 인자 방식)
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
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `venv311/bin/python -m pytest tests/test_korail_manager.py -v`
Expected: FAIL (`ModuleNotFoundError: src.core.korail_manager`)

- [ ] **Step 3: 구현 작성**

`src/core/korail_manager.py`:

```python
from src.core.rail_manager import RailManager, TrainView

# 주요 KTX 정차역 (코레일이 인식하는 한글 역명과 일치해야 함)
STATIONS = [
    "서울", "용산", "광명", "영등포", "수원", "천안아산", "오송", "대전",
    "김천구미", "서대구", "동대구", "신경주", "울산(통도사)", "부산",
    "밀양", "구포", "포항", "익산", "정읍", "광주송정", "나주", "목포",
    "여수EXPO", "순천", "전주", "남원", "마산", "창원중앙", "진주",
    "청량리", "원주", "제천", "강릉", "행신", "공주", "논산",
]

SEAT_TYPES = ["일반우선", "일반만", "특실우선", "특실만"]

PASSENGER_TYPES = [
    ("어른", "adult", 1),
    ("어린이", "child", 0),
    ("경로", "senior", 0),
    ("유아", "toddler", 0),
]


class KorailManager(RailManager):
    name = "KTX"
    STATIONS = STATIONS
    SEAT_TYPES = SEAT_TYPES
    PASSENGER_TYPES = PASSENGER_TYPES
    supports_window_seat = False
    find_id_url = "https://www.letskorail.com/korail/com/login.do"
    find_pw_url = "https://www.letskorail.com/korail/com/login.do"

    def __init__(self):
        self._korail = None
        self._id = None
        self._pw = None

    @property
    def logged_in(self) -> bool:
        return self._korail is not None

    def login(self, korail_id: str, password: str):
        try:
            from korail2 import Korail
            self._korail = Korail(korail_id, password, auto_login=True)
            self._id = korail_id
            self._pw = password
            return True, "로그인 성공"
        except Exception as e:
            self._korail = None
            return False, str(e)

    def _to_view(self, t) -> TrainView:
        return TrainView(
            train_number=getattr(t, "train_no", ""),
            dep_station_name=getattr(t, "dep_name", ""),
            arr_station_name=getattr(t, "arr_name", ""),
            dep_time=getattr(t, "dep_time", ""),
            arr_time=getattr(t, "arr_time", ""),
            general_seat_state="예약가능" if t.has_general_seat() else "매진",
            special_seat_state="예약가능" if t.has_special_seat() else "매진",
            raw=t,
        )

    def search(self, dep, arr, date, time_from, passengers=None):
        if not self._korail:
            return False, "로그인이 필요합니다"
        try:
            from korail2 import TrainType
            trains = self._korail.search_train(
                dep, arr, date, time_from,
                train_type=TrainType.KTX,
                include_no_seats=True,
            )
            return True, [self._to_view(t) for t in trains]
        except Exception as e:
            return False, str(e)

    def _build_passengers(self, passengers: dict):
        if not passengers:
            return None
        from korail2 import (AdultPassenger, ChildPassenger,
                             SeniorPassenger, ToddlerPassenger)
        mapping = [
            ("adult", AdultPassenger),
            ("child", ChildPassenger),
            ("senior", SeniorPassenger),
            ("toddler", ToddlerPassenger),
        ]
        plist = []
        for key, cls in mapping:
            n = passengers.get(key, 0)
            if n > 0:
                plist.append(cls(n))
        return plist if plist else None

    def _seat_option(self, seat_type_str: str):
        from korail2 import ReserveOption
        mapping = {
            "일반우선": ReserveOption.GENERAL_FIRST,
            "일반만": ReserveOption.GENERAL_ONLY,
            "특실우선": ReserveOption.SPECIAL_FIRST,
            "특실만": ReserveOption.SPECIAL_ONLY,
        }
        return mapping.get(seat_type_str, ReserveOption.GENERAL_FIRST)

    def reserve(self, train_view, seat_type_str="일반우선",
                window_seat=False, passengers=None):
        if not self._korail:
            return False, "로그인이 필요합니다"
        from korail2 import NeedToLoginError
        train = getattr(train_view, "raw", train_view)
        option = self._seat_option(seat_type_str)
        plist = self._build_passengers(passengers)
        try:
            reservation = self._korail.reserve(train, passengers=plist, option=option)
            return True, reservation
        except NeedToLoginError:
            ok, msg = self.login(self._id, self._pw)
            if ok:
                try:
                    reservation = self._korail.reserve(train, passengers=plist, option=option)
                    return True, reservation
                except Exception as e2:
                    return False, str(e2)
            return False, f"재로그인 실패: {msg}"
        except Exception as e:
            return False, str(e)

    def relogin(self):
        if not self._id or not self._pw:
            return False, "저장된 로그인 정보가 없습니다"
        self._korail = None
        return self.login(self._id, self._pw)

    def logout(self):
        if self._korail:
            try:
                self._korail.logout()
            except Exception:
                pass
            self._korail = None
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `venv311/bin/python -m pytest tests/test_korail_manager.py -v`
Expected: PASS (6 passed)

---

## Task 5: 철도별 설정 파일

**Files:**
- Modify: `src/config/settings.py`
- Test: `tests/test_settings.py`

`load_config(rail)` / `save_config(cfg, rail)`이 `config.srt.json` / `config.ktx.json`을 쓰도록 한다. KTX는 승객 기본값이 다르다(유아 포함, 장애 제외). 기존 `config.json`은 무시(SRT는 새 `config.srt.json` 사용).

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_settings.py`:

```python
import os
import json
import src.config.settings as settings


def test_config_path_per_rail():
    p_srt = settings._config_path("srt")
    p_ktx = settings._config_path("ktx")
    assert p_srt.endswith("config.srt.json")
    assert p_ktx.endswith("config.ktx.json")


def test_ktx_passenger_defaults_have_toddler_no_disability():
    d = settings._passenger_defaults("ktx")
    assert "toddler" in d
    assert "disability1to3" not in d


def test_srt_passenger_defaults_have_disability():
    d = settings._passenger_defaults("srt")
    assert "disability1to3" in d
    assert "toddler" not in d


def test_save_then_load_roundtrip(tmp_path, monkeypatch):
    target = tmp_path / "config.ktx.json"
    monkeypatch.setattr(settings, "_config_path", lambda rail: str(target))
    settings.save_config({"srt_id": "123", "dep_station": "서울",
                          "passengers": {"adult": 2}}, "ktx")
    loaded = settings.load_config("ktx")
    assert loaded["srt_id"] == "123"
    assert loaded["dep_station"] == "서울"
    assert loaded["passengers"]["adult"] == 2
    # 누락된 승객 키는 기본값으로 채워짐
    assert loaded["passengers"]["toddler"] == 0
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `venv311/bin/python -m pytest tests/test_settings.py -v`
Expected: FAIL (`_config_path()` 인자 없음, `_passenger_defaults` 없음)

- [ ] **Step 3: 구현 작성**

`src/config/settings.py` 전체를 다음으로 교체:

```python
import json
import os
import sys


def _passenger_defaults(rail: str) -> dict:
    if rail == "ktx":
        return {"adult": 1, "child": 0, "senior": 0, "toddler": 0}
    return {"adult": 1, "child": 0, "senior": 0,
            "disability1to3": 0, "disability4to6": 0}


def _defaults(rail: str) -> dict:
    return {
        "srt_id": "",
        "dep_station": "서울" if rail == "ktx" else "동대구",
        "arr_station": "부산" if rail == "ktx" else "수서",
        "date": "",
        "time_from": "000000",
        "time_to": "230000",
        "passengers": _passenger_defaults(rail),
        "seat_type": "일반우선",
        "window_seat": False,
        "retry_interval": 0.8,
        "discord_webhook": "",
    }


def _config_path(rail: str) -> str:
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
        base = os.path.join(base, "..", "..")
    return os.path.normpath(os.path.join(base, f"config.{rail}.json"))


def load_config(rail: str = "srt") -> dict:
    defaults = _defaults(rail)
    path = _config_path(rail)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            saved = json.load(f)
        merged = {**defaults, **saved}
        merged["passengers"] = {**defaults["passengers"],
                                **saved.get("passengers", {})}
        return merged
    return {**defaults, "passengers": {**defaults["passengers"]}}


def save_config(cfg: dict, rail: str = "srt"):
    path = _config_path(rail)
    data = {k: v for k, v in cfg.items() if k != "password"}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `venv311/bin/python -m pytest tests/test_settings.py -v`
Expected: PASS (4 passed)

---

## Task 6: ReservationWorker 철도 비종속화 + 상태 보고

**Files:**
- Modify: `src/core/reservation_worker.py`
- Test: `tests/test_reservation_worker.py`

워커가 `manager`(RailManager)를 받아 `manager.name`으로 로그하고, 매 시도마다 `on_status_callback(attempt, elapsed_seconds)`를 호출한다. 열차 표시명은 `TrainView` 속성을 쓴다.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_reservation_worker.py`:

```python
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
    # 로그에 철도명이 SRT 가 아니라 KTX 로 들어감
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
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `venv311/bin/python -m pytest tests/test_reservation_worker.py -v`
Expected: FAIL (`__init__() got unexpected keyword 'manager'` 등)

- [ ] **Step 3: 구현 작성**

`src/core/reservation_worker.py` 전체를 다음으로 교체:

```python
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
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `venv311/bin/python -m pytest tests/test_reservation_worker.py -v`
Expected: PASS (2 passed)

---

## Task 7: SearchFrame 매니저 메타데이터 구동 + 스왑/날짜 버튼

**Files:**
- Modify: `src/gui/search_frame.py`

`SearchFrame(parent, manager, on_search)`로 시그니처를 바꾸고, 역/좌석/승객/창가석을 `manager` 메타데이터에서 만든다. 출↔도 스왑 버튼과 날짜 +/- 버튼을 추가한다.

- [ ] **Step 1: 구현 작성**

`src/gui/search_frame.py` 전체를 다음으로 교체:

```python
import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta

HOURS = [f"{h:02d}0000" for h in range(24)]


class SearchFrame(ttk.LabelFrame):
    def __init__(self, parent, manager, on_search):
        super().__init__(parent, text="검색 조건")
        self.manager = manager
        self.on_search = on_search
        stations = manager.STATIONS

        # Row 1: stations + swap
        r1 = ttk.Frame(self)
        r1.pack(fill="x", padx=5, pady=3)
        ttk.Label(r1, text="출발역:").pack(side="left")
        self.dep_var = tk.StringVar(value=stations[0])
        ttk.Combobox(r1, textvariable=self.dep_var, values=stations,
                     width=10, state="readonly").pack(side="left", padx=(2, 4))
        ttk.Button(r1, text="⇄", width=3, command=self._swap).pack(side="left", padx=2)
        ttk.Label(r1, text="도착역:").pack(side="left", padx=(4, 0))
        self.arr_var = tk.StringVar(value=stations[1] if len(stations) > 1 else stations[0])
        ttk.Combobox(r1, textvariable=self.arr_var, values=stations,
                     width=10, state="readonly").pack(side="left", padx=2)

        # Row 2: date (+/-) + time
        r2 = ttk.Frame(self)
        r2.pack(fill="x", padx=5, pady=3)
        ttk.Label(r2, text="날짜:").pack(side="left")
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
        self.date_var = tk.StringVar(value=tomorrow)
        ttk.Button(r2, text="-", width=2,
                   command=lambda: self._shift_date(-1)).pack(side="left", padx=(2, 0))
        ttk.Entry(r2, textvariable=self.date_var, width=10).pack(side="left", padx=2)
        ttk.Button(r2, text="+", width=2,
                   command=lambda: self._shift_date(1)).pack(side="left", padx=(0, 15))
        ttk.Label(r2, text="시간:").pack(side="left")
        self.time_from_var = tk.StringVar(value="000000")
        ttk.Combobox(r2, textvariable=self.time_from_var, values=HOURS,
                     width=8, state="readonly").pack(side="left", padx=2)
        ttk.Label(r2, text="~").pack(side="left")
        self.time_to_var = tk.StringVar(value="230000")
        ttk.Combobox(r2, textvariable=self.time_to_var, values=HOURS,
                     width=8, state="readonly").pack(side="left", padx=2)

        # Row 3: passengers (from manager metadata)
        r3 = ttk.Frame(self)
        r3.pack(fill="x", padx=5, pady=3)
        self.pax = {}
        for label, key, default in manager.PASSENGER_TYPES:
            ttk.Label(r3, text=f"{label}:").pack(side="left")
            var = tk.IntVar(value=default)
            self.pax[key] = var
            ttk.Spinbox(r3, from_=0, to=9, textvariable=var, width=3).pack(side="left", padx=(0, 8))

        # Row 4: seat + window(optional) + search
        r4 = ttk.Frame(self)
        r4.pack(fill="x", padx=5, pady=3)
        ttk.Label(r4, text="좌석:").pack(side="left")
        self.seat_var = tk.StringVar(value=manager.SEAT_TYPES[0])
        for st in manager.SEAT_TYPES:
            ttk.Radiobutton(r4, text=st, variable=self.seat_var, value=st).pack(side="left", padx=2)

        self.window_var = tk.BooleanVar(value=False)
        if manager.supports_window_seat:
            ttk.Checkbutton(r4, text="창가석", variable=self.window_var).pack(side="left", padx=(10, 0))

        self.search_btn = ttk.Button(r4, text="검색", command=self._do_search)
        self.search_btn.pack(side="right", padx=5)

    def _swap(self):
        d, a = self.dep_var.get(), self.arr_var.get()
        self.dep_var.set(a)
        self.arr_var.set(d)

    def _shift_date(self, days: int):
        try:
            d = datetime.strptime(self.date_var.get().strip(), "%Y%m%d")
        except ValueError:
            d = datetime.now()
        self.date_var.set((d + timedelta(days=days)).strftime("%Y%m%d"))

    def _do_search(self):
        self.search_btn.configure(state="disabled")
        self.update_idletasks()
        self.on_search(self.get_params())

    def enable_search(self):
        self.search_btn.configure(state="normal")

    def get_params(self) -> dict:
        return {
            "dep": self.dep_var.get(),
            "arr": self.arr_var.get(),
            "date": self.date_var.get().strip(),
            "time_from": self.time_from_var.get(),
            "time_to": self.time_to_var.get(),
            "passengers": {k: v.get() for k, v in self.pax.items()},
            "seat_type": self.seat_var.get(),
            "window_seat": self.window_var.get(),
        }

    def load_config(self, cfg: dict):
        if cfg.get("dep_station") in self.manager.STATIONS:
            self.dep_var.set(cfg["dep_station"])
        if cfg.get("arr_station") in self.manager.STATIONS:
            self.arr_var.set(cfg["arr_station"])
        if cfg.get("date"):
            self.date_var.set(cfg["date"])
        self.time_from_var.set(cfg.get("time_from", "000000"))
        self.time_to_var.set(cfg.get("time_to", "230000"))
        for k, v in cfg.get("passengers", {}).items():
            if k in self.pax:
                self.pax[k].set(v)
        if cfg.get("seat_type") in self.manager.SEAT_TYPES:
            self.seat_var.set(cfg["seat_type"])
        self.window_var.set(cfg.get("window_seat", False))

    def get_config(self) -> dict:
        return {
            "dep_station": self.dep_var.get(),
            "arr_station": self.arr_var.get(),
            "date": self.date_var.get().strip(),
            "time_from": self.time_from_var.get(),
            "time_to": self.time_to_var.get(),
            "passengers": {k: v.get() for k, v in self.pax.items()},
            "seat_type": self.seat_var.get(),
            "window_seat": self.window_var.get(),
        }
```

- [ ] **Step 2: import 스모크 확인**

Run: `venv311/bin/python -c "from src.gui.search_frame import SearchFrame; print('ok')"`
Expected: `ok`

---

## Task 8: TrainListFrame 전체선택 + 좌석 색상

**Files:**
- Modify: `src/gui/train_list_frame.py`

`TrainView`를 그대로 받으므로 속성 접근은 유지. 전체선택/해제 체크박스와 좌석상태 색상 태그(예약가능=초록, 그 외=회색)를 추가한다.

- [ ] **Step 1: 구현 작성**

`src/gui/train_list_frame.py` 전체를 다음으로 교체:

```python
import tkinter as tk
from tkinter import ttk


class TrainListFrame(ttk.LabelFrame):
    def __init__(self, parent):
        super().__init__(parent, text="검색 결과")
        self.trains = []

        top = ttk.Frame(self)
        top.pack(fill="x", padx=5, pady=(5, 0))
        self.select_all_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text="전체선택/해제", variable=self.select_all_var,
                        command=self._toggle_all).pack(side="left")

        container = ttk.Frame(self)
        container.pack(fill="both", expand=True, padx=5, pady=5)

        columns = ("select", "train_no", "dep", "arr", "dep_time", "arr_time", "general", "special")
        self.tree = ttk.Treeview(container, columns=columns, show="headings", height=6)
        headers = [("select", "선택", 40), ("train_no", "열차번호", 70),
                   ("dep", "출발역", 70), ("arr", "도착역", 70),
                   ("dep_time", "출발", 60), ("arr_time", "도착", 60),
                   ("general", "일반석", 70), ("special", "특실", 70)]
        for key, text, width in headers:
            self.tree.heading(key, text=text)
            self.tree.column(key, width=width, anchor="center")

        self.tree.tag_configure("available", foreground="#1a7f37")
        self.tree.tag_configure("soldout", foreground="#888888")

        scrollbar = ttk.Scrollbar(container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.tree.bind("<ButtonRelease-1>", self._on_click)

        self.selected_indices = set()

    def set_trains(self, trains: list, time_to: str = "230000"):
        self.trains = []
        self.selected_indices.clear()
        self.select_all_var.set(False)
        for item in self.tree.get_children():
            self.tree.delete(item)

        for t in trains:
            dep_time = getattr(t, "dep_time", "")
            if dep_time > time_to:
                continue
            self.trains.append(t)
            train_no = getattr(t, "train_number", "")
            dep = getattr(t, "dep_station_name", "")
            arr = getattr(t, "arr_station_name", "")
            arr_time = getattr(t, "arr_time", "")
            general = getattr(t, "general_seat_state", "")
            special = getattr(t, "special_seat_state", "")
            fmt_dep = f"{dep_time[:2]}:{dep_time[2:4]}" if len(dep_time) >= 4 else dep_time
            fmt_arr = f"{arr_time[:2]}:{arr_time[2:4]}" if len(arr_time) >= 4 else arr_time
            tag = "available" if "가능" in str(general) else "soldout"
            self.tree.insert("", "end", iid=str(len(self.trains) - 1),
                             values=("", train_no, dep, arr, fmt_dep, fmt_arr, general, special),
                             tags=(tag,))

    def _toggle_all(self):
        select = self.select_all_var.get()
        self.selected_indices = set(range(len(self.trains))) if select else set()
        for i in range(len(self.trains)):
            self.tree.set(str(i), "select", "✓" if select else "")

    def _on_click(self, event):
        if self.tree.identify_region(event.x, event.y) != "cell":
            return
        item = self.tree.identify_row(event.y)
        if not item:
            return
        idx = int(item)
        if idx in self.selected_indices:
            self.selected_indices.discard(idx)
            self.tree.set(item, "select", "")
        else:
            self.selected_indices.add(idx)
            self.tree.set(item, "select", "✓")

    def get_selected_trains(self) -> list:
        return [self.trains[i] for i in sorted(self.selected_indices) if i < len(self.trains)]
```

- [ ] **Step 2: import 스모크 확인**

Run: `venv311/bin/python -c "from src.gui.train_list_frame import TrainListFrame; print('ok')"`
Expected: `ok`

---

## Task 9: ReserveFrame 시도/경과 카운터

**Files:**
- Modify: `src/gui/reserve_frame.py`

`set_status(attempt, elapsed_seconds)`로 시도 횟수와 경과 시간을 표시한다.

- [ ] **Step 1: 구현 작성**

`src/gui/reserve_frame.py` 전체를 다음으로 교체:

```python
import tkinter as tk
from tkinter import ttk


class ReserveFrame(ttk.LabelFrame):
    def __init__(self, parent, on_start, on_stop):
        super().__init__(parent, text="예매 설정")
        self.on_start = on_start
        self.on_stop = on_stop

        row = ttk.Frame(self)
        row.pack(fill="x", padx=5, pady=5)
        ttk.Label(row, text="재시도 간격:").pack(side="left")
        self.interval_var = tk.DoubleVar(value=0.8)
        ttk.Entry(row, textvariable=self.interval_var, width=5).pack(side="left", padx=(2, 2))
        ttk.Label(row, text="초").pack(side="left", padx=(0, 15))
        ttk.Label(row, text="Discord:").pack(side="left")
        self.webhook_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.webhook_var, width=30).pack(
            side="left", padx=2, fill="x", expand=True)

        btn_row = ttk.Frame(self)
        btn_row.pack(fill="x", padx=5, pady=(0, 5))
        self.start_btn = ttk.Button(btn_row, text="예매 시작", command=self.on_start)
        self.start_btn.pack(side="left", padx=5)
        self.stop_btn = ttk.Button(btn_row, text="중지", command=self.on_stop, state="disabled")
        self.stop_btn.pack(side="left", padx=5)
        self.status_var = tk.StringVar(value="대기 중")
        ttk.Label(btn_row, textvariable=self.status_var).pack(side="right", padx=5)

    def set_running(self, running: bool):
        self.start_btn.configure(state="disabled" if running else "normal")
        self.stop_btn.configure(state="normal" if running else "disabled")
        if not running:
            self.status_var.set("대기 중")

    def set_status(self, attempt: int, elapsed: float):
        m, s = divmod(int(elapsed), 60)
        self.status_var.set(f"시도 #{attempt}  경과 {m:02d}:{s:02d}")

    def load_config(self, cfg: dict):
        self.interval_var.set(cfg.get("retry_interval", 0.8))
        self.webhook_var.set(cfg.get("discord_webhook", ""))

    def get_config(self) -> dict:
        return {
            "retry_interval": self.interval_var.get(),
            "discord_webhook": self.webhook_var.get().strip(),
        }
```

- [ ] **Step 2: import 스모크 확인**

Run: `venv311/bin/python -c "from src.gui.reserve_frame import ReserveFrame; print('ok')"`
Expected: `ok`

---

## Task 10: LoginFrame 철도별 링크

**Files:**
- Modify: `src/gui/login_frame.py`

`LoginFrame(parent, manager, on_login)`로 바꾸고, 회원번호/비밀번호 찾기 링크를 `manager.find_id_url/find_pw_url`로 연다.

- [ ] **Step 1: 구현 작성**

`src/gui/login_frame.py` 전체를 다음으로 교체:

```python
import tkinter as tk
from tkinter import ttk
import webbrowser


class LoginFrame(ttk.LabelFrame):
    def __init__(self, parent, manager, on_login):
        super().__init__(parent, text="로그인")
        self.manager = manager
        self.on_login = on_login

        row = ttk.Frame(self)
        row.pack(fill="x", padx=5, pady=5)
        ttk.Label(row, text="ID:").pack(side="left")
        self.id_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.id_var, width=16).pack(side="left", padx=(2, 10))
        ttk.Label(row, text="PW:").pack(side="left")
        self.pw_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.pw_var, width=16, show="*").pack(side="left", padx=(2, 10))
        self.login_btn = ttk.Button(row, text="로그인", command=self._do_login)
        self.login_btn.pack(side="left", padx=5)

        link_row = ttk.Frame(self)
        link_row.pack(fill="x", padx=5)
        self.status_var = tk.StringVar(value="상태: 로그인 전")
        ttk.Label(link_row, textvariable=self.status_var).pack(side="left")
        ttk.Button(link_row, text="회원번호 찾기",
                   command=lambda: webbrowser.open(self.manager.find_id_url)).pack(side="right", padx=(5, 0))
        ttk.Button(link_row, text="비밀번호 찾기",
                   command=lambda: webbrowser.open(self.manager.find_pw_url)).pack(side="right", padx=(5, 0))

    def _do_login(self):
        self.login_btn.configure(state="disabled")
        self.status_var.set("상태: 로그인 중...")
        self.update_idletasks()
        self.on_login(self.id_var.get().strip(), self.pw_var.get().strip())

    def set_status(self, msg: str, success: bool = True):
        self.status_var.set(f"상태: {msg}")
        self.login_btn.configure(state="disabled" if success else "normal")

    def load_config(self, cfg: dict):
        self.id_var.set(cfg.get("srt_id", ""))
```

- [ ] **Step 2: import 스모크 확인**

Run: `venv311/bin/python -c "from src.gui.login_frame import LoginFrame; print('ok')"`
Expected: `ok`

---

## Task 11: App 에 manager 주입 + sv-ttk 테마

**Files:**
- Modify: `src/gui/app.py`

`App(manager)`로 바꾼다. 제목은 `{manager.name} 예약 매크로`, 설정은 `manager.name.lower()` 철도로 load/save, sv-ttk 테마 적용, 프레임 생성 시 manager 전달, 상태 콜백 연결.

- [ ] **Step 1: 구현 작성**

`src/gui/app.py` 전체를 다음으로 교체:

```python
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import queue

import sv_ttk

from src.gui.login_frame import LoginFrame
from src.gui.search_frame import SearchFrame
from src.gui.train_list_frame import TrainListFrame
from src.gui.reserve_frame import ReserveFrame
from src.gui.log_frame import LogFrame
from src.core.reservation_worker import ReservationWorker
from src.config.settings import load_config, save_config


class App:
    def __init__(self, manager):
        self.manager = manager
        self.rail = manager.name.lower()
        self.root = tk.Tk()
        self.root.title(f"{manager.name} 예약 매크로 v1.1")
        self.root.geometry("640x800")
        self.root.resizable(False, False)
        sv_ttk.set_theme("light")

        self.worker = None
        self.log_queue = queue.Queue()
        self.cfg = load_config(self.rail)

        self._build_ui()
        self._load_config()
        self._poll_queue()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        pad = {"padx": 10, "pady": (5, 0), "sticky": "ew"}
        self.login_frame = LoginFrame(self.root, self.manager, on_login=self._on_login)
        self.login_frame.grid(row=0, column=0, **pad)
        self.search_frame = SearchFrame(self.root, self.manager, on_search=self._on_search)
        self.search_frame.grid(row=1, column=0, **pad)
        self.train_frame = TrainListFrame(self.root)
        self.train_frame.grid(row=2, column=0, **pad)
        self.reserve_frame = ReserveFrame(self.root, on_start=self._on_reserve_start,
                                          on_stop=self._on_reserve_stop)
        self.reserve_frame.grid(row=3, column=0, **pad)
        self.log_frame = LogFrame(self.root)
        self.log_frame.grid(row=4, column=0, padx=10, pady=(5, 10), sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(4, weight=1)

    def _load_config(self):
        self.login_frame.load_config(self.cfg)
        self.search_frame.load_config(self.cfg)
        self.reserve_frame.load_config(self.cfg)

    def _save_config(self):
        cfg = {**self.cfg}
        cfg["srt_id"] = self.login_frame.id_var.get().strip()
        cfg.update(self.search_frame.get_config())
        cfg.update(self.reserve_frame.get_config())
        save_config(cfg, self.rail)

    def _on_login(self, user_id: str, password: str):
        def do():
            ok, msg = self.manager.login(user_id, password)
            self.root.after(0, lambda: self._login_done(ok, msg))
        threading.Thread(target=do, daemon=True).start()

    def _login_done(self, ok: bool, msg: str):
        self.login_frame.set_status(msg, success=ok)
        self.log_frame.append("로그인 성공" if ok else f"로그인 실패: {msg}")

    def _on_search(self, params: dict):
        if not self.manager.logged_in:
            messagebox.showwarning("경고", "먼저 로그인해주세요.")
            self.search_frame.enable_search()
            return

        def do():
            ok, result = self.manager.search(
                params["dep"], params["arr"], params["date"], params["time_from"])
            self.root.after(0, lambda: self._search_done(ok, result, params.get("time_to", "230000")))
        threading.Thread(target=do, daemon=True).start()

    def _search_done(self, ok: bool, result, time_to: str):
        self.search_frame.enable_search()
        if ok:
            self.train_frame.set_trains(result, time_to)
            self.log_frame.append(f"검색 완료: {len(self.train_frame.trains)}개 열차")
        else:
            messagebox.showerror("검색 실패", str(result))
            self.log_frame.append(f"검색 실패: {result}")

    def _on_reserve_start(self):
        selected = self.train_frame.get_selected_trains()
        if not selected:
            messagebox.showwarning("경고", "예매할 열차를 선택해주세요.")
            return
        if not self.manager.logged_in:
            messagebox.showwarning("경고", "먼저 로그인해주세요.")
            return

        params = self.search_frame.get_params()
        rcfg = self.reserve_frame.get_config()
        self.reserve_frame.set_running(True)
        self.log_frame.clear()

        self.worker = ReservationWorker(
            manager=self.manager,
            trains=selected,
            seat_type=params["seat_type"],
            window_seat=params["window_seat"],
            passengers=params.get("passengers"),
            interval=rcfg["retry_interval"],
            discord_webhook=rcfg["discord_webhook"],
            log_queue=self.log_queue,
            on_success_callback=lambda msg: self.root.after(0, lambda: self._on_success(msg)),
            on_status_callback=lambda a, e: self.root.after(0, lambda: self.reserve_frame.set_status(a, e)),
        )
        self.worker.start()

    def _on_reserve_stop(self):
        if self.worker:
            self.worker.stop()
            self.worker = None
        self.reserve_frame.set_running(False)

    def _on_success(self, msg: str):
        self.reserve_frame.set_running(False)
        self.worker = None
        messagebox.showinfo("예약 성공", msg)

    def _poll_queue(self):
        while not self.log_queue.empty():
            try:
                self.log_frame.append(self.log_queue.get_nowait())
            except queue.Empty:
                break
        self.root.after(100, self._poll_queue)

    def _on_close(self):
        if self.worker:
            self.worker.stop()
        self._save_config()
        self.manager.logout()
        self.root.destroy()

    def run(self):
        self.root.mainloop()
```

- [ ] **Step 2: import 스모크 확인**

Run: `venv311/bin/python -c "from src.gui.app import App; print('ok')"`
Expected: `ok`

---

## Task 12: 런처 + main.py

**Files:**
- Create: `src/gui/launcher.py`
- Modify: `main.py`

런처가 SRT/KTX 버튼을 띄우고, 선택 시 해당 매니저로 `App`을 실행한다.

- [ ] **Step 1: 런처 구현**

`src/gui/launcher.py`:

```python
import tkinter as tk
from tkinter import ttk

import sv_ttk


def choose_rail() -> str:
    """SRT/KTX 선택 창을 띄우고 선택값('srt'/'ktx')을 반환. 닫으면 None."""
    win = tk.Tk()
    win.title("철도 선택")
    win.geometry("320x180")
    win.resizable(False, False)
    sv_ttk.set_theme("light")

    choice = {"rail": None}

    def pick(rail):
        choice["rail"] = rail
        win.destroy()

    ttk.Label(win, text="예약할 철도를 선택하세요",
              font=("", 13)).pack(pady=(28, 18))
    btns = ttk.Frame(win)
    btns.pack()
    ttk.Button(btns, text="SRT", width=12,
               command=lambda: pick("srt")).pack(side="left", padx=8)
    ttk.Button(btns, text="KTX", width=12,
               command=lambda: pick("ktx")).pack(side="left", padx=8)

    win.mainloop()
    return choice["rail"]


def make_manager(rail: str):
    if rail == "ktx":
        from src.core.korail_manager import KorailManager
        return KorailManager()
    from src.core.srt_manager import SRTManager
    return SRTManager()
```

- [ ] **Step 2: main.py 수정**

`main.py` 전체를 다음으로 교체:

```python
import sys
import os

if getattr(sys, "frozen", False):
    os.chdir(os.path.dirname(sys.executable))
else:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

from src.gui.launcher import choose_rail, make_manager
from src.gui.app import App

if __name__ == "__main__":
    rail = choose_rail()
    if rail:
        app = App(make_manager(rail))
        app.run()
```

- [ ] **Step 3: import 스모크 확인**

Run: `venv311/bin/python -c "from src.gui.launcher import choose_rail, make_manager; print(make_manager('srt').name, make_manager('ktx').name)"`
Expected: `SRT KTX`

---

## Task 13: 전체 테스트 + 수동 스모크

**Files:** 없음 (검증 단계)

- [ ] **Step 1: 전체 단위 테스트**

Run: `venv311/bin/python -m pytest tests/ -v`
Expected: 전부 PASS (rail_manager 3, srt_manager 6, korail_manager 6, settings 4, worker 2)

- [ ] **Step 2: 런처 수동 실행 (SRT 회귀)**

Run(백그라운드): `venv311/bin/python main.py`
- 런처 창에서 **SRT** 클릭 → "SRT 예약 매크로 v1.1" 창이 sv-ttk 테마로 뜨는지
- 로그인 → 검색 → 결과에 색상 표시, 전체선택 동작
- 기존 SRT 예약 흐름이 그대로 동작하는지 확인

- [ ] **Step 3: 런처 수동 실행 (KTX)**

Run(백그라운드): `venv311/bin/python main.py`
- 런처에서 **KTX** 클릭 → "KTX 예약 매크로" 창, 역 목록이 KTX(서울/부산 등), 승객에 "유아" 있고 "장애" 없음, 창가석 체크박스 없음 확인
- **코레일 계정으로 로그인 → 검색**까지 사용자가 직접 확인(실서버 연동은 자동 검증 불가). 로그인 실패 시 에러 메시지가 명확히 뜨는지 확인

- [ ] **Step 4: 설정 분리 확인**

SRT/KTX 각각에서 역/날짜를 바꾼 뒤 창을 닫고 다시 열어 `config.srt.json` / `config.ktx.json`이 따로 저장·복원되는지 확인.

---

## Self-Review 결과

- **스펙 커버리지**: KTX 예약(Task 4), 런처(Task 12), 추상화/TrainView(Task 2~4), GUI 메타데이터 구동(Task 7~10), sv-ttk(Task 11), 철도별 설정(Task 5), 창가석 미지원 처리(Task 7), 승객 차이(Task 3·4), 시도/경과 카운터(Task 6·9) — 모두 태스크로 매핑됨.
- **미검증 항목**: korail2 ↔ 코레일 실서버 연동은 Task 13 Step 3에서 사용자 수동 확인으로 처리(설계 명시 사항).
- **타입 일관성**: `TrainView`/`RailManager` 시그니처, `manager.name/STATIONS/SEAT_TYPES/PASSENGER_TYPES/supports_window_seat`, `ReservationWorker(manager=...)`, `load_config(rail)/save_config(cfg, rail)`, `set_status(attempt, elapsed)` 가 모든 태스크에서 동일하게 사용됨.
