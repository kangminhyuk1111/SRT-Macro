# KTX 지원 추가 + GUI 현대화 설계

날짜: 2026-06-21
대상: srtMacro (SRT 예약 매크로) → SRT/KTX 통합 매크로

## 1. 목표

- 기존 SRT 예약 매크로에 **KTX(코레일) 예약** 기능을 추가한다.
- SRT와 KTX는 **별도 철도로 분리**하되, **하나의 패키지/exe로 배포**한다.
- 앱 시작 시 **SRT / KTX 선택 화면(런처)** 을 띄우고, 고른 철도의 창을 연다.
- GUI를 **현대적 테마(sv-ttk) + 실용 개선** 으로 다듬는다.
- 외부 라이브러리 추가는 `korail2`, `sv-ttk` 두 개로 한정한다.

## 2. 검증 완료된 사실 (구현 전 확인됨)

- `korail2==0.4.0` 설치·import OK. 주요 API:
  - `Korail(korail_id, korail_pw, auto_login=True)`
  - `search_train(dep, arr, date, time, train_type='100'(KTX), passengers=None, include_no_seats=False)`
  - `reserve(train, passengers=None, option='GENERAL_FIRST', try_waiting=False)`
  - 승객: `AdultPassenger(count=1)`, `ChildPassenger`, `SeniorPassenger`, `ToddlerPassenger` — **개수 인자 방식**, 장애 승객 클래스 없음
  - 좌석옵션 `ReserveOption.GENERAL_FIRST/GENERAL_ONLY/SPECIAL_FIRST/SPECIAL_ONLY` (문자열)
  - 열차 속성: `train_no, dep_name, arr_name, dep_time, arr_time, train_type_name, has_general_seat(), has_special_seat(), reserve_possible_name`
- `sv-ttk` 설치·import OK (라이트/다크 모던 테마).
- 미검증(통제 불가): `korail2`의 **코레일 실서버 연동**은 계정이 없어 실제 로그인/예약 확인 불가. → KTX 로그인 실패 시 명확한 에러 메시지로 처리.

## 3. 호환성/의존성 판단

- **열차 객체 정규화는 필수.** GUI/워커가 SRT 속성(`train_number`, `dep_station_name`, `general_seat_state`)을 직접 읽는데 KTX는 이름이 다르고 일부가 메서드(`has_general_seat()`)다. 정규화 없이는 KTX가 화면에 안 뜬다.
- **추상화가 위험을 만드는 게 아니라 호환성 문제를 격리한다.** 승객 API 차이(개수 인자 vs 인스턴스)도 매니저 내부에 가둔다.
- **import는 지연(lazy) 처리.** 각 매니저의 `login()` 내부에서 라이브러리를 import → 한쪽 라이브러리가 없어도 그 철도를 고를 때만 에러.
- 두 라이브러리 모두 순수 파이썬(+requests)이라 충돌·무게 문제 없음.

## 4. 아키텍처

### 4.1 RailManager 추상화

공통 인터페이스(덕타이핑/베이스 클래스):

```
class RailManager:
    name: str                      # "SRT" / "KTX"
    STATIONS: list[str]            # 철도별 역 목록
    SEAT_TYPES: list[str]          # 좌석 라디오 항목
    PASSENGER_TYPES: list[tuple]   # (label, key, default) 승객 입력 항목
    supports_window_seat: bool     # SRT=True, KTX=False (korail reserve엔 창가석 옵션 없음)
    find_id_url: str               # 회원번호 찾기 링크
    find_pw_url: str               # 비밀번호 찾기 링크

    def login(id, pw) -> (bool, msg)
    def search(dep, arr, date, time_from, passengers=None) -> (bool, list[TrainView] | err)
    def reserve(train_view, seat_type, window_seat, passengers) -> (bool, reservation | err)
    def relogin() -> (bool, msg)
    def logout()
```

- `SRTManager`(기존 정리) / `KorailManager`(신규) 두 구현.
- `search()`는 라이브러리 열차를 **`TrainView`로 정규화**해 반환.

### 4.2 TrainView (정규화 어댑터)

GUI/워커가 읽는 통일된 속성 + 원본 참조:

```
TrainView:
    train_number: str
    dep_station_name / arr_station_name: str
    dep_time / arr_time: str          # "HHMMSS"
    general_seat_state: str           # "예약가능" / "매진" 등 한글
    special_seat_state: str
    raw: object                       # 원본 SRT/Korail 열차 (reserve에 전달)
```

- SRT: 기존 속성 매핑.
- KTX: `train_no→train_number`, `dep_name→dep_station_name`, `has_general_seat()→"예약가능"/"매진"` 등으로 변환.
- 워커는 `TrainView`를 `manager.reserve()`에 넘기고, 매니저가 `.raw`를 꺼내 라이브러리에 전달.

### 4.3 좌석/승객 차이 흡수

- 좌석: SRT `SEAT_TYPE_MAP`(SeatType), KTX `ReserveOption` 매핑을 각 매니저가 보유.
- 승객: 매니저 내부 `_build_passengers(dict)`가 철도별로 변환.
  - SRT: 어른/어린이/경로/장애1~3/장애4~6 (인스턴스 1개=1명)
  - KTX: 어른/어린이/경로/유아 (개수 인자), 장애 항목 없음
- GUI `SearchFrame`은 `manager.PASSENGER_TYPES`로 입력 칸을 동적 생성.

### 4.4 런처 (시작 선택 화면)

- `main.py` → `Launcher` 창(작게): "SRT" / "KTX" 버튼.
- 선택 시 해당 `RailManager` 인스턴스 + 메타데이터로 `App` 생성, 런처 창은 닫음.
- 같은 앱·같은 패키지, 코드만 매니저로 분기.

## 5. GUI 변경 (sv-ttk 모던 + 실용 개선)

- **테마**: 앱 시작 시 `sv_ttk.set_theme("light")` 적용(다크 토글 버튼 옵션).
- **런처**: 깔끔한 2버튼 선택 창.
- **LoginFrame**: 회원번호/비밀번호 찾기 링크를 `manager.find_id_url/find_pw_url`로 (철도별).
- **SearchFrame**:
  - 출발↔도착 **스왑 버튼(⇄)**.
  - 날짜 **+/- 버튼**(오타 방지, 수동 입력도 유지).
  - 역 목록/좌석/승객 항목을 `manager` 메타데이터로 구동.
  - **창가석 체크박스는 `manager.supports_window_seat`가 True일 때만 표시** (KTX는 숨김).
- **TrainListFrame**:
  - **전체선택 / 전체해제** 체크.
  - 좌석 상태 **색상 태그**: 예약가능=초록, 매진=회색.
- **ReserveFrame**:
  - **시도 횟수 + 경과 시간** 카운터 표시(워커가 상태 보고).
- **ReservationWorker**: 철도 하드코딩 제거 → `manager.name` 사용, 상태(시도수/경과) 큐로 보고.

## 6. 설정 / 배포

- 설정 파일 **철도별 분리**: `config.srt.json` / `config.ktx.json`. 각자 역·날짜·승객 기억.
- `config/settings.py`의 load/save가 철도명을 받아 해당 파일 사용.
- `requirements.txt`에 `korail2`, `sv-ttk` 추가.
- PyInstaller로 단일 exe에 SRT/KTX 모두 포함.

## 7. 영향 받는 파일

| 파일 | 변경 |
|---|---|
| `main.py` | 런처 호출로 변경 |
| `src/gui/launcher.py` | **신규** — SRT/KTX 선택 창 |
| `src/core/rail_manager.py` | **신규** — RailManager 베이스 + TrainView |
| `src/core/srt_manager.py` | RailManager 구현으로 정리, search가 TrainView 반환, lazy import |
| `src/core/korail_manager.py` | **신규** — KorailManager |
| `src/core/reservation_worker.py` | 철도 비종속화, 상태 보고 |
| `src/gui/app.py` | manager 주입, sv-ttk 적용, 제목 동적 |
| `src/gui/login_frame.py` | 링크 철도별 |
| `src/gui/search_frame.py` | stations/seat/passenger 동적, 스왑·날짜 버튼 |
| `src/gui/train_list_frame.py` | 전체선택, 색상 태그 |
| `src/gui/reserve_frame.py` | 시도/경과 카운터 |
| `src/config/settings.py` | 철도별 설정 파일 |
| `requirements.txt` | korail2, sv-ttk 추가 |

## 8. 테스트 전략

- **SRTManager → TrainView 정규화**: 기존 SRT 검색 결과가 정규화 후에도 동일하게 표시되는지(회귀).
- **KorailManager 정규화**: mock/실제 korail 열차 객체 속성 매핑 단위 검증.
- **승객 변환**: SRT/KTX 각각 `_build_passengers`가 올바른 객체/개수 생성하는지.
- **GUI 메타데이터 구동**: 매니저 교체 시 역/좌석/승객 칸이 바뀌는지.
- **런처**: SRT/KTX 선택 → 올바른 매니저로 App 생성.
- KTX 실서버 로그인은 사용자 계정으로 수동 확인(자동화 불가).

## 9. 범위 밖 (YAGNI)

- SRT/KTX 동시 검색·예약.
- 자동결제, 좌석 지정(호차/번호) 세부 선택.
- 대기예약(try_waiting) — 1차 범위에서 제외, 추후 옵션.
