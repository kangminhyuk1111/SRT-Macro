# SRTrain → npm 포팅 및 Node 백엔드 전환 설계

작성일: 2026-07-19
근거 소스:
- `venv311/lib/python3.11/site-packages/SRT/` (srt.py, netfunnel.py, constants.py, passenger.py, reservation.py, train.py, errors.py, response_data.py, seat_type.py)
- `server/app.py` (교체 대상 FastAPI 백엔드)
- `web/lib/api.ts` (프론트가 의존하는 REST 계약)
- `src/core/reservation_worker.py`, `src/core/srt_manager.py` (재시도 루프·에러 처리)

---

## 1. 목표와 산출물

| # | 산출물 | 설명 |
|---|--------|------|
| 1 | **`srt-client`** (npm 라이브러리) | SRTrain(Python, ~1,500줄) 을 TypeScript 로 재구현한 순수 HTTP 클라이언트. Node 전용 (SRT 서버가 CORS 를 허용하지 않으므로 브라우저 직접 호출 불가). |
| 2 | **Node 백엔드** | `server/app.py` 와 **동일한 REST 스펙** 을 제공하는 서버. `web/lib/api.ts` 는 REST 계약만 의존하므로 프론트 무수정 교체. |
| 3 | **`npx` 통합 패키지** | `npx srt-macro` 한 줄로 Node 서버 + Next.js 정적 빌드 프론트를 함께 실행하는 배포 패키지. Python/venv 설치 불필요. |

비목표(Non-goals):
- KTX(korail) 포팅은 이번 범위 밖 (백엔드는 `rail` 파라미터 구조를 유지해 나중에 끼워 넣을 수 있게만 설계).
- 결제(`pay_with_card`)·예약대기(`reserve_standby`)는 API 표면만 정의하고 Phase 1 필수 범위에서 제외 가능 (매크로 핵심 플로우는 login → search → reserve).

---

## 2. `srt-client` 라이브러리 설계

### 2.1 모듈 구조

```
srt-client/
├── src/
│   ├── constants.ts     # STATION_CODE, TRAIN_NAME, API_ENDPOINTS, USER_AGENT, WINDOW_SEAT ...
│   ├── errors.ts        # SRTError 계층
│   ├── types.ts         # 원시 API 응답 타입(RawTrain, RawReservation ...) + 공개 타입
│   ├── session.ts       # 쿠키 유지 fetch 래퍼 (undici + tough-cookie)
│   ├── netfunnel.ts     # NetFunnelHelper (키 발급/대기/완료/캐시)
│   ├── response.ts      # SRTResponseData 대응 파서 (resultMap / strResult / msgCd)
│   ├── passenger.ts     # Passenger 계층 + combine + form dict 생성
│   ├── train.ts         # SRTTrain (검색 결과 모델)
│   ├── reservation.ts   # SRTReservation, SRTTicket
│   ├── client.ts        # SRT 클래스 (login/search/reserve/cancel/getReservations ...)
│   └── index.ts         # 공개 API re-export
└── test/
    ├── fixtures/        # 실 응답 캡처 JSON/텍스트
    └── *.test.ts
```

Python 원본과 파일 단위 1:1 대응을 유지해, 업스트림(SRTrain) 변경 시 diff 추적을 쉽게 한다.

### 2.2 포팅할 상수 테이블 (constants.ts — 실제 값)

`SRT/constants.py` 를 그대로 옮긴다. **값을 임의로 바꾸지 말 것** — 서버가 검증하는 리버스 엔지니어링 값이다.

**역 코드 `STATION_CODE`** (34개 항목, 전체 이관):

```ts
export const STATION_CODE: Record<string, string> = {
  "수서": "0551", "동탄": "0552", "평택지제": "0553", "곡성": "0049",
  "공주": "0514", "광주송정": "0036", "구례구": "0050", "김천(구미)": "0507",
  "나주": "0037", "남원": "0048", "대전": "0010", "동대구": "0015",
  "마산": "0059", "목포": "0041", "밀양": "0017", "부산": "0020",
  "서대구": "0506", "순천": "0051", "신경주": "0508", "경주": "0508",
  "여수EXPO": "0053", "여천": "0139", "오송": "0297", "울산(통도사)": "0509",
  "익산": "0030", "전주": "0045", "정읍": "0033", "진영": "0056",
  "진주": "0063", "창원": "0057", "창원중앙": "0512", "천안아산": "0502",
  "포항": "0515",
};
export const STATION_NAME = Object.fromEntries(
  Object.entries(STATION_CODE).map(([k, v]) => [v, k])); // 주의: "경주"가 "신경주"를 덮음 — Python dict 역변환과 동일 동작 유지
```

**열차 종별 `TRAIN_NAME`**: `"17": "SRT"` 가 핵심. `"00": "KTX"`, `"07"/"10": "KTX-산천"`, `"08": "ITX-새마을"`, `"09": "ITX-청춘"`, `"18": "ITX-마음"`, `"02": "무궁화"`, `"03": "통근열차"`, `"04": "누리로"`, `"05": "전체"`.

**창측 좌석 코드 `WINDOW_SEAT`** (Python 은 `None/True/False` 키 — TS 에서는 함수로):

```ts
export function windowSeatCode(w: boolean | null | undefined): string {
  return w === true ? "012" : w === false ? "013" : "000";
}
```

**엔드포인트 `API_ENDPOINTS`** (base `SRT_MOBILE = "https://app.srail.or.kr:443"`):

| key | path |
|---|---|
| main | `/main/main.do` |
| login | `/apb/selectListApb01080_n.do` |
| logout | `/login/loginOut.do` |
| search_schedule | `/ara/selectListAra10007_n.do` |
| reserve | `/arc/selectListArc05013_n.do` |
| tickets | `/atc/selectListAtc14016_n.do` |
| ticket_info | `/ard/selectListArd02017_n.do?` (원본에 트레일링 `?` 포함 — 그대로 유지) |
| cancel | `/ard/selectListArd02045_n.do` |
| standby_option | `/ata/selectListAta01135_n.do` |
| payment | `/ata/selectListAta09036_n.do` |

**User-Agent** (iPhone SRT 앱 위장 — 정확히 이 문자열):

```
Mozilla/5.0 (iPhone; CPU iPhone OS 18_0_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 SRT-APP-iOS V.2.0.18
```

**기타 상수**:
- `INVALID_NETFUNNEL_KEY = "NET000001"` (검색 응답 msgCd — 키 만료 시 재발급 트리거)
- `RESERVE_JOBID = { PERSONAL: "1101", STANDBY: "1102" }`
- 결과 코드 `"SUCC"` / `"FAIL"` (resultMap[0].strResult)
- 승객 타입 코드 (passenger.py / reservation.py `PASSENGER_TYPE`): `"1"` 어른/청소년, `"2"` 장애 1~3급, `"3"` 장애 4~6급, `"4"` 경로, `"5"` 어린이
- 좌석 등급 `psrmClCd`: `"1"` 일반실, `"2"` 특실
- 좌석 요구 `rqSeatAttCd`: `"015"` 일반 (휠체어 `"021"` 은 원본도 미지원), 방향 `dirSeatAttCd`: `"009"`, `smkSeatAttCd`/`etcSeatAttCd`: `"000"`

### 2.3 세션/쿠키 처리 (권장안)

`requests.Session` 은 쿠키를 자동 관리하지만 Node 의 `fetch` 는 하지 않는다. **권장: `undici` + `tough-cookie` 로 얇은 `Session` 클래스를 직접 구현** 한다.

- `undici` 는 Node 내장 fetch 의 기반 라이브러리로 별도 무거운 의존성이 없고, `CookieJar`(tough-cookie) 와 조합해 요청 전 `Cookie` 헤더 주입 / 응답의 `set-cookie` 수집만 하면 된다 (~50줄).
- 대안 검토: `axios` + `axios-cookiejar-support` (의존성 큼), `got` (v12+ ESM-only 제약), `undici` 의 `CookieAgent`(`http-cookie-agent`) — 어느 쪽도 가능하나 표준 fetch API 표면을 유지하는 undici 직접 조합이 가장 이식성이 좋다.

```ts
// session.ts
export class Session {
  private jar = new CookieJar();
  headers: Record<string, string>; // { "User-Agent": USER_AGENT, "Accept": "application/json" }

  async postForm(url: string, data: Record<string, string | number | null | undefined>): Promise<string>;
  async get(url: string, params: Record<string, string>): Promise<string>;
}
```

주의점:
- 요청 본문은 **`application/x-www-form-urlencoded`** (Python `requests` 의 `data=` 와 동일). `URLSearchParams` 사용. `null`/`undefined` 값은 Python 이 `None` 을 `"None"` 문자열로 보내지 않도록 requests 가 처리하는 방식과 달리, **빈 문자열로 직렬화하거나 키 자체를 유지**해야 하므로 실제 요청 캡처로 검증 필요 (특히 reserve 의 `mblPhone: None`).
- `set-cookie` 다중 헤더는 `response.headers.getSetCookie()` (undici/Node 20+) 로 수집.
- NetFunnel 은 **별도 세션** (`http://nf.letskorail.com` — HTTP, 쿠키 도메인 분리)을 쓴다. Python 원본도 `NetFunnelHelper` 가 자체 `requests.session()` 을 갖는다.

### 2.4 핵심 플로우 명세

#### 2.4.1 login — 로그인 타입 판별

`POST /apb/selectListApb01080_n.do`. ID 형식으로 `srchDvCd` 결정:

```ts
const EMAIL_REGEX = /[^@]+@[^@]+\.[^@]+/;
const PHONE_NUMBER_REGEX = /(\d{3})-(\d{3,4})-(\d{4})/;
// 이메일 → "2", 전화번호 → "3" (하이픈 제거 후 전송), 그 외 멤버십번호 → "1"
```

폼 필드: `auto: "Y"`, `check: "Y"`, `page: "menu"`, `deviceKey: "-"`, `customerYn: ""`, `login_referer: <main URL>`, `srchDvCd`, `srchDvNm: <id>`, `hmpgPwdCphd: <pw>`.

실패 판정은 **응답 본문 문자열 검사** (원본과 동일하게):
- `"존재하지않는 회원입니다"` 포함 → `SRTLoginError(json.MSG)`
- `"비밀번호 오류"` 포함 → `SRTLoginError(json.MSG)`
- `"Your IP Address Blocked due to abnormal access."` 포함 → `SRTLoginError(body)`

성공 시 `userMap.MB_CRD_NO` 를 `membershipNumber` 로 저장 (결제 시 필요). 세션 쿠키가 로그인 상태의 전부이므로 CookieJar 유지가 필수.

```ts
async login(id?: string, pw?: string): Promise<boolean>;
```

#### 2.4.2 searchTrain — 페이징 반복 조회

`POST /ara/selectListAra10007_n.do`. 요청 필드(고정값 포함): `chtnDvCd: "1"`(직통), `arriveTime: "N"`, `seatAttCd: "015"`, `psgNum: 1`(검색은 1명 기준), `trnGpCd: 109`, `stlbTrnClsfCd: "05"`(전체), `dptDt`, `dptTm`, `arvRsStnCd`, `dptRsStnCd`, `netfunnelKey`.

알고리즘 (srt.py `_search_train` 재현):
1. NetFunnel 키 발급 (캐시 사용).
2. 1차 조회. 실패 시 `msgCd === "NET000001"` 이고 캐시 사용 중이면 → **캐시 무시하고 새 키로 딱 1회 재귀 재시도** (`use_netfunnel_cache=false`). 그 외 실패는 `SRTResponseError(msgTxt, msgCd)`.
3. 응답 `outDataSets.dsOutput1` → `SRTTrain[]`. API 는 **부분 목록만 반환**하므로:
   - 마지막 열차의 `dep_time` 을 `HHmmss` 로 파싱해 **+1초** 한 값을 `dptTm` 으로 재조회, 결과를 이어붙인다.
   - `time_limit` 을 넘었거나, 재조회가 `FAIL`(더 이상 열차 없음)이면 중단.
4. 필터: `train_name === "SRT"` 만 (KTX 등 제거) → `available_only` 면 `seat_available()` 만 → `time_limit` 이하만.

```ts
async searchTrain(dep: string, arr: string, opts?: {
  date?: string;        // yyyyMMdd, default 오늘
  time?: string;        // hhmmss, default "000000"
  timeLimit?: string;
  availableOnly?: boolean; // default true (매크로는 false 로 호출)
}): Promise<SRTTrain[]>;
```

좌석 판정 (train.py): `generalSeatState.includes("예약가능")`, 특실 동일, 예약대기는 `rsvWaitPsbCd` 에 `"9"` 포함 여부.

#### 2.4.3 reserve — jobId 1101

`POST /arc/selectListArc05013_n.do`, `jobId: "1101"` (+`reserveType: "11"` — PERSONAL 전용).

**좌석 등급 결정 로직** — 검색 시점 잔여석 문자열 기반 (srt.py 431~446행 재현):

```ts
type SeatType = "GENERAL_FIRST" | "GENERAL_ONLY" | "SPECIAL_FIRST" | "SPECIAL_ONLY";
// GENERAL_ONLY → special=false / SPECIAL_ONLY → special=true
// GENERAL_FIRST → train.generalSeatAvailable() ? false : true
// SPECIAL_FIRST → train.specialSeatAvailable() ? true : false
```

폼 필드 (열차 목록 값 그대로 전달): `jrnyCnt: "1"`, `jrnyTpCd: "11"`, `jrnySqno1: "001"`, `stndFlg: "N"`, `trnGpCd1: "300"`, `trnGpCd: "109"`, `grpDv: "0"`, `rtnDv: "0"`, `stlbTrnClsfCd1`, `dptRsStnCd1`/`dptRsStnCdNm1`, `arvRsStnCd1`/`arvRsStnCdNm1`, `dptDt1`, `dptTm1`, `arvTm1`, **`trnNo1`: 열차번호 5자리 zero-pad** (`"%05d"`), `runDt1`(=dptDt1), `dptStnConsOrdr1`/`arvStnConsOrdr1`/`dptStnRunOrdr1`/`arvStnRunOrdr1`(검색 응답의 구성/운행 순서 — SRTTrain 이 보존해야 함), `mblPhone`, `netfunnelKey`.

**승객 dict 생성** (passenger.ts): 동일 타입 승객을 `combine` 으로 병합 후, `totPrnb`(총 인원), `psgGridcnt`(승객 타입 수), 그리고 타입별 인덱스 i(1부터)에 대해:
- `psgTpCd{i}`: 타입 코드 (어른 "1" / 장애1~3 "2" / 장애4~6 "3" / 경로 "4" / 어린이 "5")
- `psgInfoPerPrnb{i}`: 해당 타입 인원 수
- `locSeatAttCd{i}`: `windowSeatCode(windowSeat)` ("000"/"012"/"013")
- `rqSeatAttCd{i}: "015"`, `dirSeatAttCd{i}: "009"`, `smkSeatAttCd{i}: "000"`, `etcSeatAttCd{i}: "000"`
- `psrmClCd{i}`: 특실이면 `"2"`, 일반실 `"1"`

**성공 후 pnrNo 매칭**: 예약 응답의 `reservListMap[0].pnrNo` 를 얻은 뒤, `getReservations()` 로 전체 예약 목록을 재조회해 `reservation_number === pnrNo` 인 `SRTReservation` 을 찾아 반환. 못 찾으면 `SRTError("Ticket not found: check reservation status")`. (예약 응답 자체에는 결제기한 등 상세가 없기 때문.)

```ts
async reserve(train: SRTTrain, opts?: {
  passengers?: Passenger[];    // default [new Adult()]
  specialSeat?: SeatType;      // default "GENERAL_FIRST"
  windowSeat?: boolean | null;
}): Promise<SRTReservation>;
```

#### 2.4.4 getReservations / ticketInfo / cancel

- `getReservations(paidOnly = false)`: `POST tickets` (`pageNo: "0"`) → `trainListMap` 과 `payListMap` 을 zip, 각 예약마다 `ticketInfo(pnrNo)` 를 추가 호출(N+1 — 원본 그대로) 해 `SRTReservation` 조립. `paidOnly` 면 `pay.stlFlg === "N"` 제외.
- `ticketInfo(pnrNo)`: `POST ticket_info` (`pnrNo`, `jrnySqno: "1"`) → `trainListMap` → `SRTTicket[]`.
- `cancel(pnrNo)`: `POST cancel` (`pnrNo`, `jrnyCnt: "1"`, `rsvChgTno: "0"`).

#### 2.4.5 NetFunnel 헬퍼 (netfunnel.ts)

대기열 통과 프로토콜: `GET http://nf.letskorail.com/ts.wseq` (HTTP!), 응답은 JS 문자열 (`NetFunnel.gRtype=...;NetFunnel.gControl.result='5002:200:key=...&nwait=...';`).

| 단계 | opcode | 파라미터 | 비고 |
|---|---|---|---|
| 키 발급 | `5101` (getTidchkEnter) | `nfid=0`, `prefix=NetFunnel.gRtype=5101;`, `sid=service_1`, `aid=act_10`, `js=true`, `{epoch_ms}=` (캐시버스터 — **밀리초 타임스탬프가 파라미터 키**) | status `201`(WAIT_FAIL) 이면 대기열 진입 |
| 대기 체크 | `5002` (chkEnter) | + `key`, `ttl=1` | `nwait > 0` 이면 1초 sleep 후 재귀. 새 key 로 갱신하며 반복 |
| 완료 | `5004` (setComplete) | + `key` | status 가 `200`(PASS) 또는 `502`(ALREADY_COMPLETED) 가 아니면 `SRTNetFunnelError` |

`generateNetfunnelKey(useCache)` = `getKey(useCache)` → `setComplete(key)` → key 반환.

**캐시·만료 처리 (이번에 고친 버그 반영)**:
- 발급한 키는 `cachedKey` 에 캐시. `useCache=true` 고 캐시가 있으면 네트워크 호출 없이 반환.
- 키 만료 징후 2가지, 모두 처리해야 함:
  1. **검색/예약 응답**의 `msgCd === "NET000001"` (INVALID_NETFUNNEL_KEY) → client.ts 가 캐시 무시 재시도 (2.4.2 참조).
  2. **setComplete 응답**이 `5004:503` `"Wrong Server ID"` → `SRTNetFunnelError`. 만료 키를 캐시한 채로는 모든 요청이 계속 실패하므로, **헬퍼에 `resetCache(): void` 공개 메서드를 두고**, 상위(매니저/워커)가 `SRTNetFunnelError` catch 시 `resetCache()` 후 1회 재시도한다 (`src/core/srt_manager.py` 의 `reset_netfunnel_cache` + search/reserve 의 catch-retry 패턴, `reservation_worker.py` 의 시작 시 캐시 초기화 재현). Python 원본은 private `_cached_key = None` 을 외부에서 찌르는 구조였는데, TS 포팅에서는 공개 API 로 승격한다.

```ts
export class NetFunnelHelper {
  async generateNetfunnelKey(useCache: boolean): Promise<string>;
  resetCache(): void;
}
```

응답 파서는 원본 `NetFunnelResponse.parse` 와 동일하게 `;` 분리 → `NetFunnel.gControl.result='<code>:<status>:<k=v&...>'` 에서 `key`, `nwait`, `status` 추출. 정규식 한 개로 단순화 가능하나 포맷 변형 대비해 원본 로직 유지 권장.

#### 2.4.6 응답 파서 (response.ts)

`resultMap[0]` 에서 `strResult`("SUCC"/"FAIL"), `msgTxt`, `msgCd` 추출. `resultMap` 이 없고 `ErrorCode`/`ErrorMsg` 가 있으면 `SRTResponseError`, 그 외 `SRTError`. JSON 파싱 실패 시 `SRTResponseError("Failed to decode: invalid response (<body>)")`.

### 2.5 에러 체계 매핑 (errors.ts)

| Python | JS/TS | 비고 |
|---|---|---|
| `SRTError(msg, code?)` | `class SRTError extends Error { code?: string }` | `toString` = `msg [code]` |
| `SRTLoginError` | `class SRTLoginError extends SRTError` | 기본 메시지 "Login failed, please check ID/PW" |
| `SRTResponseError(msg, code?)` | `class SRTResponseError extends SRTError` | `code` 에 msgCd (예: "NET000001") |
| `SRTDuplicateError` | `class SRTDuplicateError extends SRTResponseError` | |
| `SRTNotLoggedInError` | `class SRTNotLoggedInError extends SRTError` | 워커의 재로그인 트리거 |
| `SRTNetFunnelError` | `class SRTNetFunnelError extends Error` | 원본도 SRTError 를 상속하지 않음 — 동일 유지. 캐시 리셋 트리거 |

`Object.setPrototypeOf(this, new.target.prototype)` 로 `instanceof` 를 보장하고, 에러 클래스는 전부 export 한다 (상위 레이어의 `instanceof SRTNetFunnelError` 분기가 핵심 로직이므로).

### 2.6 TypeScript 타입 정의 방향

- **원시 응답 타입과 도메인 모델을 분리**: `types.ts` 에 `RawTrainData`(dsOutput1 요소: `stlbTrnClsfCd`, `trnNo`, `dptDt`, `dptTm`, `dptRsStnCd`, `arvDt`, `arvTm`, `arvRsStnCd`, `gnrmRsvPsbStr`, `sprmRsvPsbStr`, `rsvWaitPsbCd`, `arvStnRunOrdr`, `arvStnConsOrdr`, `dptStnRunOrdr`, `dptStnConsOrdr` ...) 등을 정의하고, `SRTTrain`/`SRTReservation`/`SRTTicket` 클래스는 이를 받아 camelCase 필드로 노출.
- 도메인 모델은 **직렬화 가능**해야 함 (REST 응답으로 그대로 내보내기 위해 `toJSON()` 제공). Python 의 `dump()` 문자열 표현도 `toString()` 으로 유지 (로그 메시지 호환).
- 미지의 필드가 많으므로 raw 타입은 `& Record<string, string>` 인덱스 시그니처 허용.
- 열차/역 코드 미등록 시 원본과 동일하게 `"알 수 없는 ... (업데이트 필요)"` 폴백.

### 2.7 테스트 전략 (실서버 무의존)

원칙: **네트워크 계층(Session)만 목킹하고 나머지는 실코드로 검증**. 실서버 호출 테스트는 만들지 않는다 (비공개 API + 계정 필요 + IP 차단 리스크).

- **fixture 수집**: 기존 Python 매크로 실행 시 `verbose` 로그 또는 mitmproxy 로 실제 응답을 캡처해 `test/fixtures/` 에 저장 — `login_success.json`, `login_wrong_pw.json`, `search_page1.json`/`search_page2.json`(페이징 검증용), `search_netfunnel_expired.json`(NET000001), `reserve_success.json`, `tickets.json`, `netfunnel_5101_pass.txt`, `netfunnel_5101_wait.txt`, `netfunnel_5004_wrong_server_id.txt`. 개인정보(회원번호, pnrNo)는 마스킹.
- **단위 테스트** (vitest 권장):
  - `response.ts`: SUCC/FAIL/ErrorCode/비JSON 파싱.
  - `netfunnel.ts`: 응답 문자열 파싱, 대기열 재귀(nwait 감소 시나리오, fake timer), 5004:503 → 에러, 캐시 반환/리셋.
  - `passenger.ts`: combine 병합, form dict 생성 스냅샷 (Python 출력과 필드 단위 대조 — **골든 테스트**: Python 쪽에서 동일 입력의 `get_passenger_dict` 출력을 fixture 로 저장해 비교).
  - `client.ts`: Session 을 목킹해 (a) 로그인 타입 판별 3종 + 전화번호 하이픈 제거, (b) 검색 페이징 (+1초 재조회, FAIL 중단, SRT 필터, time_limit), (c) NET000001 → 캐시 미사용 재시도 1회 (무한 재귀 방지 검증), (d) 좌석 등급 결정 4 케이스, (e) reserve 폼 필드 스냅샷 (trnNo1 zero-pad 포함), (f) pnrNo 매칭 실패 → SRTError.
- **요청 대조 테스트**가 가장 중요: Python 구현으로 만든 요청 폼 body 를 fixture 로 떠서 TS 구현의 출력과 키/값 단위로 diff. 이것이 "서버 없이 포팅 정확성" 을 담보하는 핵심 장치다.

---

## 3. Node 백엔드 설계

### 3.1 REST 스펙 (server/app.py 에서 추출 — 이 계약을 그대로 유지해야 프론트 무수정)

에러 응답 형식: HTTP 4xx/5xx + body `{ "detail": string }` (web/lib/api.ts 가 `body.detail` 을 읽음 — **FastAPI 의 HTTPException 형식을 Node 에서도 유지**).

| 메서드 | 경로 | 요청 | 응답 | 에러 |
|---|---|---|---|---|
| GET | `/api/meta` | - | `{ [rail]: { name, stations: string[], seat_types: string[], passenger_types: {label,key,default}[], supports_window_seat } }` | - |
| GET | `/api/state` | - | `{ rail, logged_in, running, attempt, elapsed, success_message, train_count }` | - |
| POST | `/api/login` | `{ rail, user_id, password }` | `{ message }` | 400 unknown rail / 409 예매 진행 중 / 401 로그인 실패(msg) |
| POST | `/api/logout` | - | `{ message: "로그아웃" }` | 409 예매 진행 중 |
| POST | `/api/search` | `{ dep, arr, date(yyyyMMdd), time_from(hhmmss) }` | `{ trains: [{ index, train_number, dep_station_name, arr_station_name, dep_time, arr_time, general_seat_state, special_seat_state }] }` | 401 미로그인 / 502 검색 실패 |
| POST | `/api/reserve/start` | `{ train_indices: number[], seat_type="일반우선", window_seat=false, passengers: {adult,child,senior,disability1to3,disability4to6}, interval=0.8, discord_webhook="" }` | `{ message: "예매 시작" }` | 401 / 409 이미 진행 중 / 400 인덱스 불일치·빈 선택 |
| POST | `/api/reserve/stop` | - | `{ message: "중지 요청" }` | - |
| GET | `/api/logs?after=N` | - | `{ logs: string[], next: number }` | - |
| DELETE | `/api/logs` | - | `{ message: "cleared" }` | - |
| GET | `/api/config/{rail}` | - | config JSON | 400 unknown rail |
| PUT | `/api/config/{rail}` | 부분 config | `{ message: "saved" }` | 400 unknown rail (기존 config 와 merge 저장) |

세부 계약 사항:
- 검색 시 SRTManager 는 `available_only: false` 로 호출 (매진 열차도 목록에 표시 후 매크로 대상 선택).
- `seat_type` 값: `"일반우선" | "일반만" | "특실우선" | "특실만"` (한국어 문자열이 그대로 계약).
- 상태는 **프로세스 전역 단일 상태** (로컬 단일 사용자 전제) — Node 도 동일하게 모듈 스코프 `AppState` 하나.
- 로그는 폴링 방식: 누적 배열 + `after` 오프셋. `HH:MM:SS ` 접두 타임스탬프.
- config 저장 위치는 기존 `src/config/settings.py` 와 호환 (`config.json`, gitignore 됨) — 동일 파일 포맷/경로를 읽고 쓰면 마이그레이션 없음.
- CORS: 개발 중 Next dev 서버(3000)에서 접근하므로 `Access-Control-Allow-Origin: *` 유지. (Phase 3 에서 동일 오리진 서빙이 되면 사실상 불필요하지만 계약 유지 차원에서 남긴다.)

프레임워크: **Fastify 권장** (경량, 스키마 검증 내장, Express 대비 유지보수 활발). Hono 도 대안. `RailManager` 인터페이스를 두어 KTX 매니저를 나중에 추가할 수 있게 한다:

```ts
interface RailManager {
  readonly name: string;
  readonly meta: RailMeta;               // /api/meta 응답 조각
  loggedIn: boolean;
  login(id: string, pw: string): Promise<Result<string>>;
  relogin(): Promise<Result<string>>;
  logout(): Promise<void>;
  search(dep: string, arr: string, date: string, timeFrom: string): Promise<Result<TrainView[]>>;
  reserve(train: TrainView, seatType: string, windowSeat: boolean,
          passengers?: Record<string, number>): Promise<Result<SRTReservation>>;
  resetNetfunnelCache(): void;
}
```

### 3.2 SRTManager 포팅 (src/core/srt_manager.py 재현)

에러 처리 정책을 그대로 옮긴다 — 이 계층이 매크로 안정성의 핵심:
- `search`: `SRTNetFunnelError` catch → `resetNetfunnelCache()` → 1회 재시도. 그 외 예외는 `(false, message)`.
- `reserve`: (1) `SRTNetFunnelError` → 캐시 리셋 후 1회 재시도, (2) `SRTNotLoggedInError` → 저장된 ID/PW 로 재로그인 후 1회 재시도, (3) 그 외 → 실패 메시지 반환 (예외를 던지지 않음 — 워커 루프가 계속 돌아야 하므로).
- 좌석 타입 매핑: `"일반우선"→GENERAL_FIRST`, `"일반만"→GENERAL_ONLY`, `"특실우선"→SPECIAL_FIRST`, `"특실만"→SPECIAL_ONLY` (미지정 시 GENERAL_FIRST).
- 승객 빌드: `{adult:1}` 기본, count 만큼 인스턴스 생성 (라이브러리 쪽 `combine` 이 병합).

### 3.3 예매 워커 루프 (reservation_worker.py 재현)

Python 은 `threading.Thread` + `Event` 였다. Node 는 단일 스레드이므로 **`async` 무한 루프 + `AbortController`** 로 재현한다. `setInterval` 은 부적합 — reserve 호출(수백 ms~수 초)이 인터벌보다 길면 요청이 겹치고, 순차성이 보장되지 않는다.

```ts
class ReservationWorker {
  private abort = new AbortController();
  running = false;

  start(): void { this.running = true; void this.loop(); }  // fire-and-forget
  stop(): void { this.abort.abort(); }

  private async loop(): Promise<void> {
    this.manager.resetNetfunnelCache();          // 시작 시 만료 키 제거 (버그 재발 방지)
    await sendDiscord(this.webhook, `${rail} 예약 매크로를 시작합니다.`);
    this.log("예매 시작");
    let attempt = 0;
    const startTime = Date.now();
    let lastRelogin = startTime;
    const RELOGIN_INTERVAL_MS = 60_000;

    while (!this.abort.signal.aborted) {
      if (Date.now() - lastRelogin >= RELOGIN_INTERVAL_MS) {   // 60초 재로그인
        this.log("세션 유지를 위해 재로그인 중...");
        const { ok, msg } = await this.manager.relogin();
        this.log(ok ? "재로그인 성공" : `재로그인 실패: ${msg}`);
        lastRelogin = Date.now();
      }
      const train = this.trains[attempt % this.trains.length]; // 라운드로빈
      attempt++;
      this.onStatus?.(attempt, (Date.now() - startTime) / 1000); // elapsed 초 단위 유지
      this.log(`#${attempt} 시도 - ${trainName}`);
      const { ok, result } = await this.manager.reserve(train, this.seatType, this.windowSeat, this.passengers);
      if (ok) { /* 성공 로그 + Discord + onSuccess(msg) 후 return */ }
      this.log(`  실패: ${result}`);
      if (this.intervalMs > 0) await sleep(this.intervalMs, this.abort.signal); // abort 시 즉시 탈출
    }
    this.log("예매 중지됨");
  }
}
```

원본과 동일하게 유지할 동작:
- 시작 직후 **NetFunnel 캐시 초기화** (이전 실행의 만료 키 → "Wrong Server ID" 연쇄 실패 방지 — 이번에 고친 버그).
- **60초마다 재로그인** (`relogin()` = 새 SRT 인스턴스로 재생성. 재로그인은 새 세션이므로 NetFunnel 캐시도 함께 새 헬퍼로 초기화됨).
- 대상 열차 **라운드로빈** 순회, 실패해도 루프 지속, `interval` 초 sleep (기본 0.8s).
- 성공 시 즉시 종료 + Discord 알림 (`sendDiscord` 는 webhook URL 빈 값이면 no-op, fetch POST 한 줄).
- `sleep` 은 abort signal 을 받아 stop 요청 시 interval 대기를 끊는다 (Python `Event.is_set` 폴링보다 응답성 개선).
- `/api/state` 의 `running` 은 `worker.running` (loop 종료/성공/중지 시 false 로 내림 — Python 의 `Thread.is_alive()` 대응).

---

## 4. npm 패키징

### 4.1 패키지 구성

모노레포 내 2 패키지 또는 단일 패키지 + 서브패스. 권장: **단일 배포 패키지 `srt-macro`** 안에 라이브러리를 `srt-macro/client` 서브패스로 노출 (배포 단순화; 라이브러리 단독 수요가 생기면 그때 분리).

```jsonc
// package.json (핵심 필드)
{
  "name": "srt-macro",
  "type": "module",
  "bin": { "srt-macro": "./dist/cli.js" },        // npx srt-macro
  "exports": {
    ".": "./dist/index.js",                        // 서버 프로그래매틱 API
    "./client": "./dist/client/index.js"           // srt-client 라이브러리
  },
  "types": "./dist/index.d.ts",
  "files": ["dist", "web-dist"],                   // 빌드 산출물 + Next 정적 빌드
  "engines": { "node": ">=20" },                   // fetch/getSetCookie/AbortSignal 안정판
  "dependencies": { "fastify": "...", "@fastify/static": "...", "@fastify/cors": "...",
                     "undici": "...", "tough-cookie": "..." }
}
```

- `cli.js`: 포트 파싱(`--port`, 기본 8000) → Fastify 기동 → 브라우저 자동 오픈(`open` 또는 안내 메시지만).
- 빌드: `tsup` 또는 `tsc` (ESM 단일 타깃, Node 전용이므로 CJS 듀얼 빌드 불필요).

### 4.2 Next.js 프론트 동봉

- `web/` 을 `output: "export"` (정적 export) 로 빌드 → `web-dist/` 로 복사해 npm 패키지에 포함.
- Node 서버가 `@fastify/static` 으로 `web-dist/` 를 루트에 서빙, `/api/*` 는 API 라우트. **동일 오리진**이 되므로 `NEXT_PUBLIC_API_BASE` 는 빈 문자열(상대 경로)로 빌드 — `web/lib/api.ts` 1행의 `|| 'http://localhost:8000'` 폴백 때문에 빌드 시 `NEXT_PUBLIC_API_BASE=""` 를 명시적으로 지정해야 함 (코드 수정 없이 환경변수로 해결 가능; 빈 문자열이 falsy 라 폴백이 타면 그때만 프론트 1행 수정 필요 — Phase 3 에서 확인).
- 프론트가 SSR 기능을 쓰지 않는지(현재 폴링 기반 CSR 구조) export 가능성만 확인하면 됨.

### 4.3 배포 채널

- **1순위: npm publish** (public). `npx srt-macro@latest` 로 항상 최신 실행 — 비공식 API 가 자주 바뀌는 특성상 사용자가 자동으로 최신 수정을 받는 것이 중요.
- 보조: GitHub Releases + `npm i -g github:kangminhyuk/srtMacro` 형태. npm 정책(매크로성 도구) 리스크가 걱정되면 GitHub Packages 로 이전 가능.
- `config.json`(계정정보) 는 패키지에 절대 포함 금지 — 실행 시 사용자 홈(`~/.srt-macro/config.json`) 에 생성하도록 config 경로를 CWD 의존에서 홈 디렉터리 기준으로 조정 (npx 실행 CWD 는 임의 위치이므로).

---

## 5. 마이그레이션 단계별 계획

### Phase 1 — `srt-client` 라이브러리 포팅 + 테스트

작업: constants/errors/types → session → response → netfunnel → passenger/train/reservation → client 순서로 포팅. Python 실행으로 fixture 캡처 (요청 body + 응답).

**완료 기준**:
1. 2.7 의 단위 테스트 전부 통과 (커버리지: netfunnel 파서, 검색 페이징, NET000001 재시도, 좌석등급 4케이스, 승객 dict 골든 테스트).
2. Python vs TS **요청 폼 body 필드 단위 diff = 0** (login/search/reserve 각 1케이스 이상).
3. 실계정 스모크 테스트 1회 (수동): 로그인 → 검색 → (빈 좌석 열차) 예약 → 예약 확인 → 취소 성공.

### Phase 2 — Node 백엔드

작업: Fastify 서버 + SRTManager/ReservationWorker 포팅. FastAPI 서버와 **병행 운용** 가능하게 동일 포트 스펙(8000) 유지.

**완료 기준**:
1. 3.1 스펙 표의 전 엔드포인트에 대한 계약 테스트 통과 — FastAPI 응답과 JSON 구조 diff = 0 (에러 케이스의 `{detail}` 형식 포함).
2. 기존 Next 프론트(`web/`)를 **한 줄도 수정하지 않고** `NEXT_PUBLIC_API_BASE=http://localhost:8000` 으로 Node 서버에 붙여 로그인→검색→예매시작→로그폴링→중지 전 과정 동작.
3. 워커 시나리오 테스트: 60초 재로그인 발화, stop 즉시 중단, NetFunnel 키 만료 주입 시 자동 복구(캐시 리셋 재시도) — manager 목킹 기반.
4. 1시간 이상 연속 매크로 실행 시 메모리/소켓 누수 없음 (수동 관찰).

### Phase 3 — npx 통합 패키징

작업: Next 정적 export + 동봉 서빙, `bin` CLI, config 홈 디렉터리 이전, npm publish (또는 사전 `npm pack` 검증).

**완료 기준**:
1. 깨끗한 머신(Python 미설치)에서 `npx srt-macro` → 브라우저 UI 로 실제 예매 플로우 완주.
2. `npm pack` 산출물에 config/계정정보/소스맵 외 불필요 파일 미포함.
3. README 에 설치/실행/업데이트(`npx srt-macro@latest`) 안내.
4. FastAPI 서버(`server/app.py`)와 Python 코어를 저장소에서 deprecated 표기 (삭제는 안정화 후).

---

## 6. 리스크와 대응

| 리스크 | 내용 | 대응 |
|---|---|---|
| **비공식 API 변경** | SRT 앱 업데이트로 엔드포인트/필드/UA 검증이 바뀌면 즉시 전체 기능 마비. 암호화가 없어 지금은 단순하지만, 향후 서명 도입 가능성도 있음 | **SRTrain 업스트림 follow 전략**: (1) 파일 구조를 1:1 로 유지했으므로 업스트림 릴리스 diff 를 그대로 TS 에 반영하는 절차를 README 에 문서화, (2) GitHub Actions 로 SRTrain(ryanking13/SRT) 저장소 릴리스를 주기 감시(RSS/API) 해 이슈 자동 생성, (3) constants.ts 상단에 "SRTrain vX.Y.Z 기준" 버전 마커 주석 유지 |
| NetFunnel 프로토콜 변경 | letskorail 대기열은 SRT 와 별개 사업자 시스템 — 응답 포맷이 조용히 바뀔 수 있음 | 파서에 관용적 실패 메시지(원문 포함) + fixture 기반 테스트로 회귀 감지. "Wrong Server ID" 류 미분류 에러는 일단 캐시 리셋 재시도로 흡수 |
| IP 차단 | "Your IP Address Blocked" — 과도한 폴링 시 발생 | interval 하한(예: 0.3s) 가드, 차단 감지 시 워커 자동 중지 + 명확한 로그 |
| requests ↔ undici 직렬화 차이 | `None` 값 폼 필드, 인코딩(EUC-KR 아님 확인됨 — UTF-8), 헤더 순서 등 미묘한 차이로 서버가 거부할 수 있음 | Phase 1 의 요청 diff 테스트가 방어선. 실패 시 mitmproxy 로 Python/Node 요청 바이트 대조 |
| 유지보수 부담 | Python(기존 데스크톱 앱)과 Node 이중 스택 기간 발생 | Phase 2 완료 시점부터 Python 서버 기능 동결(버그픽스만), Phase 3 후 deprecated. 데스크톱(src/gui) 유지 여부는 별도 결정 |
| npm 배포 정책 | 예매 매크로 성격상 npm/저작권 이슈 소지 | 패키지 설명을 중립적으로, 문제 시 GitHub 배포로 전환 (4.3) |
| Node 버전 파편화 | `getSetCookie` 등 Node 20+ API 의존 | `engines.node >= 20` 강제 + CLI 시작 시 버전 체크로 친절한 에러 |
