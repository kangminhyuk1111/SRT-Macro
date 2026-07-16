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
