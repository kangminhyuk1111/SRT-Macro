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

    # korail2 0.4.0 버그 우회: 라이브러리는 로그인에만 최신 버전('231231001')을 쓰고
    # 검색/예약에는 2019년 값(self._version='190617001')을 그대로 보내 코레일이
    # "최신 버전으로 업데이트" 오류로 거부한다. 로그인이 통과시킨 버전을 전 요청에 적용한다.
    # 코레일이 최소 버전을 올려 다시 거부하면 이 값을 갱신해야 한다.
    KORAIL_VERSION = "231231001"

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
            # 검색/예약도 로그인이 통과시킨 최신 버전을 쓰도록 덮어쓴다.
            self._korail._version = self.KORAIL_VERSION
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
