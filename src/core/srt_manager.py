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
