'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { api, AppStatus, RailMeta, Train } from '@/lib/api';

const HOURS = Array.from({ length: 24 }, (_, h) =>
  String(h).padStart(2, '0'),
);

function fmtTime(t: string) {
  return t.length >= 4 ? `${t.slice(0, 2)}:${t.slice(2, 4)}` : t;
}

function fmtElapsed(sec: number) {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return m > 0 ? `${m}분 ${s}초` : `${s}초`;
}

function todayISO() {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

/** 좌석 상태: 색 dot + 텍스트 (색만으로 구분 금지) */
function SeatState({ state }: { state: string }) {
  const ok = state.includes('가능');
  return (
    <span className={`st ${ok ? 'st--ok' : 'st--err'}`}>
      <span className="st__dot" />
      {state}
    </span>
  );
}

export default function Home() {
  const [meta, setMeta] = useState<Record<string, RailMeta> | null>(null);
  const [rail, setRail] = useState('srt');
  const [status, setStatus] = useState<AppStatus | null>(null);
  const [error, setError] = useState('');

  // 로그인
  const [userId, setUserId] = useState('');
  const [password, setPassword] = useState('');
  const [loggingIn, setLoggingIn] = useState(false);

  // 검색
  const [dep, setDep] = useState('');
  const [arr, setArr] = useState('');
  const [date, setDate] = useState(todayISO());
  const [timeFrom, setTimeFrom] = useState('06');
  const [timeTo, setTimeTo] = useState('23');
  const [searching, setSearching] = useState(false);
  const [trains, setTrains] = useState<Train[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());

  // 예매 옵션
  const [seatType, setSeatType] = useState('일반우선');
  const [windowSeat, setWindowSeat] = useState(false);
  const [passengers, setPassengers] = useState<Record<string, number>>({});
  const [interval_, setInterval_] = useState(0.8);
  const [webhook, setWebhook] = useState('');

  // 로그
  const [logs, setLogs] = useState<string[]>([]);
  const logCursor = useRef(0);
  const logBoxRef = useRef<HTMLDivElement>(null);

  // 예약 성공 모달 (닫은 메시지는 세션 내 다시 띄우지 않음)
  const [dismissedMsg, setDismissedMsg] = useState<string | null>(null);
  const notifiedMsg = useRef<string | null>(null);

  const railMeta = meta?.[rail];
  const loggedIn = Boolean(status?.logged_in && status.rail === rail);
  const running = Boolean(status?.running);
  const dryRun = Boolean(status?.dry_run);
  const successMsg = status?.success_message ?? null;
  const showSuccessModal = Boolean(successMsg && successMsg !== dismissedMsg);

  const loadConfig = useCallback(async (r: string, m: RailMeta) => {
    try {
      const cfg = await api.getConfig(r);
      setUserId(String(cfg.srt_id ?? ''));
      setPassword(String(cfg.password ?? ''));
      setDep(String(cfg.dep_station ?? m.stations[0]));
      setArr(String(cfg.arr_station ?? m.stations[1]));
      setSeatType(String(cfg.seat_type ?? m.seat_types[0]));
      setWindowSeat(Boolean(cfg.window_seat));
      setInterval_(Number(cfg.retry_interval ?? 0.8));
      setWebhook(String(cfg.discord_webhook ?? ''));
      const saved = (cfg.passengers ?? {}) as Record<string, number>;
      const p: Record<string, number> = {};
      for (const pt of m.passenger_types) p[pt.key] = saved[pt.key] ?? pt.default;
      setPassengers(p);
    } catch {
      const p: Record<string, number> = {};
      for (const pt of m.passenger_types) p[pt.key] = pt.default;
      setPassengers(p);
      setDep(m.stations[0]);
      setArr(m.stations[1]);
    }
  }, []);

  // 초기 로드
  useEffect(() => {
    (async () => {
      try {
        const m = await api.meta();
        setMeta(m);
        const st = await api.state();
        setStatus(st);
        const r = st.rail && m[st.rail] ? st.rail : 'srt';
        setRail(r);
        await loadConfig(r, m[r]);
      } catch {
        setError('백엔드에 연결할 수 없습니다. 서버가 실행 중인지 확인해주세요.');
      }
    })();
  }, [loadConfig]);

  // 상태 폴링 (1초)
  useEffect(() => {
    const t = setInterval(async () => {
      try {
        setStatus(await api.state());
        setError((e) =>
          e === '백엔드에 연결할 수 없습니다. 서버가 실행 중인지 확인해주세요.' ? '' : e,
        );
      } catch {
        /* 다음 폴링에서 재시도 */
      }
    }, 1000);
    return () => clearInterval(t);
  }, []);

  // 로그 폴링 (0.7초)
  useEffect(() => {
    const t = setInterval(async () => {
      try {
        const r = await api.logs(logCursor.current);
        if (r.logs.length > 0) {
          logCursor.current = r.next;
          setLogs((prev) => [...prev, ...r.logs].slice(-500));
        }
      } catch {
        /* 다음 폴링에서 재시도 */
      }
    }, 700);
    return () => clearInterval(t);
  }, []);

  // 로그 자동 스크롤
  useEffect(() => {
    const box = logBoxRef.current;
    if (box) box.scrollTop = box.scrollHeight;
  }, [logs]);

  // 예약 성공 → 시스템 알림 (권한이 이미 granted인 경우)
  useEffect(() => {
    if (!successMsg || notifiedMsg.current === successMsg) return;
    notifiedMsg.current = successMsg;
    if (
      typeof window !== 'undefined' &&
      'Notification' in window &&
      Notification.permission === 'granted'
    ) {
      try {
        new Notification('예약 성공', { body: successMsg });
      } catch {
        /* 알림 실패는 무시 */
      }
    }
  }, [successMsg]);

  const switchRail = async (r: string) => {
    if (r === rail || running || !meta) return;
    setRail(r);
    setTrains([]);
    setSelected(new Set());
    setError('');
    await loadConfig(r, meta[r]);
  };

  const doLogin = async () => {
    if (!userId || !password) {
      setError('아이디와 비밀번호를 입력해주세요.');
      return;
    }
    setLoggingIn(true);
    setError('');
    try {
      await api.login(rail, userId, password);
      setStatus(await api.state());
      await api.putConfig(rail, { srt_id: userId, password });
    } catch (e) {
      setError(`로그인 실패: ${(e as Error).message}`);
    } finally {
      setLoggingIn(false);
    }
  };

  const doLogout = async () => {
    try {
      await api.logout();
      setStatus(await api.state());
      setTrains([]);
      setSelected(new Set());
      setError('');
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const doSearch = async () => {
    setSearching(true);
    setError('');
    try {
      const dateCompact = date.replaceAll('-', '');
      const r = await api.search(dep, arr, dateCompact, `${timeFrom}0000`);
      const limit = `${timeTo}5959`;
      setTrains(r.trains.filter((t) => t.dep_time <= limit));
      setSelected(new Set());
      await api.putConfig(rail, {
        dep_station: dep,
        arr_station: arr,
        date: dateCompact,
        time_from: `${timeFrom}0000`,
        time_to: `${timeTo}0000`,
      });
    } catch (e) {
      setError(`검색 실패: ${(e as Error).message}`);
    } finally {
      setSearching(false);
    }
  };

  const toggleTrain = (idx: number) => {
    if (running) return;
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  };

  const toggleAll = () => {
    if (running) return;
    setSelected((prev) =>
      prev.size === trains.length
        ? new Set()
        : new Set(trains.map((t) => t.index)),
    );
  };

  const doStart = async () => {
    setError('');
    // 예매 시작 시 브라우저 알림 권한 요청 (아직 미정인 경우)
    if (
      typeof window !== 'undefined' &&
      'Notification' in window &&
      Notification.permission === 'default'
    ) {
      Notification.requestPermission().catch(() => {});
    }
    try {
      await api.clearLogs();
      logCursor.current = 0;
      setLogs([]);
      await api.reserveStart({
        train_indices: [...selected],
        seat_type: seatType,
        window_seat: windowSeat,
        passengers,
        interval: interval_,
        discord_webhook: webhook,
      });
      setStatus(await api.state());
      await api.putConfig(rail, {
        seat_type: seatType,
        window_seat: windowSeat,
        passengers,
        retry_interval: interval_,
        discord_webhook: webhook,
      });
    } catch (e) {
      setError(`예매 시작 실패: ${(e as Error).message}`);
    }
  };

  const doStop = async () => {
    try {
      await api.reserveStop();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const toggleDryRun = async (enabled: boolean) => {
    try {
      await api.setDryRun(enabled);
      setStatus(await api.state());
    } catch (e) {
      setError((e as Error).message);
    }
  };

  /* ── 상단 네비 ── */
  const nav = (
    <header className="nav">
      <div className="nav__brand">
        <span className="nav__dot" aria-hidden />
        <span className="nav__title">기차 예약 매크로</span>
        <span className="nav__sep">/</span>
        <span className="nav__sub">예매 콘솔</span>
      </div>
      <div className="nav__right">
        {meta && (
          <nav className="nav-tabs" aria-label="철도 선택">
            {Object.entries(meta).map(([key, m]) => (
              <button
                key={key}
                className={rail === key ? 'active' : ''}
                disabled={running}
                onClick={() => switchRail(key)}
              >
                {m.name}
              </button>
            ))}
          </nav>
        )}
        {loggedIn && (
          <button className="nav__logout" onClick={doLogout} disabled={running}>
            로그아웃
          </button>
        )}
      </div>
    </header>
  );

  /* ── 로딩 ── */
  if (!meta) {
    return (
      <>
        {nav}
        <main className="login-wrap">
          <div className="card fade-in" style={{ width: 380 }}>
            <div className="card__head">
              <span className="card__title">예매 콘솔</span>
              <span className="card__hint">localhost:8000</span>
            </div>
            <div className="card__body">
              {error ? (
                <span className="st st--err">
                  <span className="st__dot" />
                  {error}
                </span>
              ) : (
                <span className="st st--idle">
                  <span className="st__dot" />
                  불러오는 중...
                </span>
              )}
            </div>
          </div>
        </main>
      </>
    );
  }

  /* ── 로그인 화면 (6:4 카드) ── */
  if (!loggedIn) {
    return (
      <>
        {nav}
        <main className="login-wrap">
          <div className="login-card fade-in">
            <section className="login-intro">
              <h1>
                SRT/KTX
                <br />
                자동 예매 콘솔
              </h1>
              <div className="flow" aria-label="동작 방식">
                <span className="step">열차 검색</span>
                <span className="arr">→</span>
                <span className="step">매진 열차 선택</span>
                <span className="arr">→</span>
                <span className="step">잔여석 발생 시 자동 예약</span>
              </div>
              <ul>
                <li>0.8초 간격(조정 가능)으로 좌석을 자동 재시도합니다.</li>
                <li>예약 성공 시 디스코드 웹훅으로 즉시 알림을 보냅니다.</li>
                <li>
                  예약 성공 후에는 결제기한 내에 SRT/코레일 공식 앱에서 직접
                  결제해야 합니다.
                </li>
                <li>여러 열차를 동시에 걸어두고 먼저 잡히는 좌석을 예약합니다.</li>
              </ul>
              <p className="local-note">
                이 콘솔은 사용자의 PC에서 로컬로 실행되며, 모든 요청은 개인
                IP로 직접 전송됩니다.
              </p>
            </section>
            <section className="login-form">
              <h2>로그인</h2>
              <div className="rail-select" role="tablist" aria-label="철도 선택">
                {Object.entries(meta).map(([key, m]) => (
                  <button
                    key={key}
                    role="tab"
                    aria-selected={rail === key}
                    className={rail === key ? 'active' : ''}
                    onClick={() => switchRail(key)}
                  >
                    {m.name}
                  </button>
                ))}
              </div>
              <div className="field">
                <label htmlFor="login-id">아이디</label>
                <input
                  id="login-id"
                  value={userId}
                  onChange={(e) => setUserId(e.target.value)}
                  placeholder="멤버십번호 / 이메일 / 전화번호"
                  autoComplete="username"
                />
              </div>
              <div className="field">
                <label htmlFor="login-pw">비밀번호</label>
                <input
                  id="login-pw"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && doLogin()}
                  autoComplete="current-password"
                />
              </div>
              <button
                className="btn btn--primary btn--block"
                onClick={doLogin}
                disabled={loggingIn}
              >
                {loggingIn ? <span className="spin" /> : `${railMeta?.name} 로그인`}
              </button>
              {error && <div className="error-note">{error}</div>}
            </section>
          </div>
        </main>
      </>
    );
  }

  /* ── 예매 콘솔 ── */
  return (
    <>
      {nav}
      <main className="shell fade-in">
        <div className="page-head">
          <h1>예매 콘솔</h1>
          <p>
            {railMeta?.name} · <span className="mono">{userId}</span> 계정으로
            로그인됨
          </p>
        </div>

        {/* 열차 검색 */}
        <section className="card">
          <div className="card__head">
            <span className="card__title">열차 검색</span>
            <span className="card__hint">GET /api/search</span>
          </div>
          <div className="card__body">
            <div className="row">
              <div className="field">
                <label htmlFor="dep">출발역</label>
                <select id="dep" value={dep} onChange={(e) => setDep(e.target.value)}>
                  {railMeta?.stations.map((s) => (
                    <option key={s}>{s}</option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label htmlFor="arr">도착역</label>
                <select id="arr" value={arr} onChange={(e) => setArr(e.target.value)}>
                  {railMeta?.stations.map((s) => (
                    <option key={s}>{s}</option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label htmlFor="date">날짜</label>
                <input
                  id="date"
                  type="date"
                  value={date}
                  min={todayISO()}
                  onChange={(e) => setDate(e.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="time-from">출발 시각</label>
                <select
                  id="time-from"
                  value={timeFrom}
                  onChange={(e) => setTimeFrom(e.target.value)}
                >
                  {HOURS.map((h) => (
                    <option key={h} value={h}>
                      {h}시
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label htmlFor="time-to">~ 까지</label>
                <select
                  id="time-to"
                  value={timeTo}
                  onChange={(e) => setTimeTo(e.target.value)}
                >
                  {HOURS.map((h) => (
                    <option key={h} value={h}>
                      {h}시
                    </option>
                  ))}
                </select>
              </div>
              <button
                className="btn btn--primary"
                onClick={doSearch}
                disabled={searching || running}
              >
                {searching ? <span className="spin" /> : '검색'}
              </button>
            </div>
          </div>
        </section>

        {/* 열차 선택 */}
        {trains.length > 0 && (
          <section className="card">
            <div className="card__head">
              <span className="card__title">열차 선택</span>
              <span className="card__hint">
                {selected.size}/{trains.length} selected
              </span>
            </div>
            <div className="card__body card__body--flush">
              <table className="vtable">
                <thead>
                  <tr>
                    <th style={{ width: 36 }}>
                      <input
                        type="checkbox"
                        aria-label="전체 선택"
                        checked={selected.size === trains.length && trains.length > 0}
                        onChange={toggleAll}
                        disabled={running}
                      />
                    </th>
                    <th>열차</th>
                    <th>구간</th>
                    <th>출발</th>
                    <th>도착</th>
                    <th>일반실</th>
                    <th>특실</th>
                  </tr>
                </thead>
                <tbody>
                  {trains.map((t) => (
                    <tr
                      key={t.index}
                      className={`selectable ${selected.has(t.index) ? 'selected' : ''}`}
                      onClick={() => toggleTrain(t.index)}
                    >
                      <td>
                        <input
                          type="checkbox"
                          checked={selected.has(t.index)}
                          onChange={() => toggleTrain(t.index)}
                          onClick={(e) => e.stopPropagation()}
                          disabled={running}
                        />
                      </td>
                      <td>
                        {railMeta?.name}{' '}
                        <span className="mono">{t.train_number}</span>
                      </td>
                      <td>
                        {t.dep_station_name} → {t.arr_station_name}
                      </td>
                      <td className="mono">{fmtTime(t.dep_time)}</td>
                      <td className="mono">{fmtTime(t.arr_time)}</td>
                      <td>
                        <SeatState state={t.general_seat_state} />
                      </td>
                      <td>
                        <SeatState state={t.special_seat_state} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {/* 예매 옵션 */}
        <section className="card">
          <div className="card__head">
            <span className="card__title">예매 옵션</span>
            <span className="card__hint">POST /api/reserve/start</span>
          </div>
          <div className="card__body">
            <div className="row" style={{ marginBottom: 16 }}>
              <div className="field">
                <label htmlFor="seat-type">좌석 유형</label>
                <select
                  id="seat-type"
                  value={seatType}
                  disabled={running}
                  onChange={(e) => setSeatType(e.target.value)}
                >
                  {railMeta?.seat_types.map((s) => (
                    <option key={s}>{s}</option>
                  ))}
                </select>
              </div>
              {railMeta?.supports_window_seat && (
                <div className="field">
                  <label htmlFor="window-seat">창가 우선</label>
                  <input
                    id="window-seat"
                    type="checkbox"
                    checked={windowSeat}
                    disabled={running}
                    onChange={(e) => setWindowSeat(e.target.checked)}
                    style={{ marginTop: 9 }}
                  />
                </div>
              )}
              {railMeta?.passenger_types.map((pt) => (
                <div className="field" key={pt.key}>
                  <label htmlFor={`pt-${pt.key}`}>{pt.label}</label>
                  <input
                    id={`pt-${pt.key}`}
                    type="number"
                    min={0}
                    max={9}
                    value={passengers[pt.key] ?? 0}
                    disabled={running}
                    onChange={(e) =>
                      setPassengers((prev) => ({
                        ...prev,
                        [pt.key]: Math.max(0, Number(e.target.value) || 0),
                      }))
                    }
                    style={{ width: 64 }}
                  />
                </div>
              ))}
              <div className="field">
                <label htmlFor="interval">재시도 간격(초)</label>
                <input
                  id="interval"
                  type="number"
                  step={0.1}
                  min={0.1}
                  value={interval_}
                  disabled={running}
                  onChange={(e) => setInterval_(Number(e.target.value) || 0.8)}
                  style={{ width: 90 }}
                />
              </div>
              <div className="field" style={{ flex: 1, minWidth: 220 }}>
                <label htmlFor="webhook">디스코드 웹훅 (선택)</label>
                <input
                  id="webhook"
                  value={webhook}
                  disabled={running}
                  onChange={(e) => setWebhook(e.target.value)}
                  placeholder="https://discord.com/api/webhooks/..."
                />
              </div>
            </div>
            <div className="run-bar">
              {running ? (
                <button className="btn btn--danger" onClick={doStop}>
                  예매 중지
                </button>
              ) : (
                <button
                  className="btn btn--primary"
                  onClick={doStart}
                  disabled={selected.size === 0}
                >
                  예매 시작 ({selected.size}개 열차{dryRun ? ' · 드라이런' : ''})
                </button>
              )}
              {running ? (
                <>
                  <span className="st st--warn">
                    <span className="st__dot" />
                    실행 중
                  </span>
                  <span className="stat">
                    시도<b>{status?.attempt ?? 0}회</b>
                  </span>
                  <span className="stat">
                    경과<b>{fmtElapsed(status?.elapsed ?? 0)}</b>
                  </span>
                  <span className="spin" />
                </>
              ) : (
                <span className="st st--idle">
                  <span className="st__dot" />
                  대기 중
                </span>
              )}
              <span className="dryrun-toggle">
                <label htmlFor="dry-run">
                  <input
                    id="dry-run"
                    type="checkbox"
                    checked={dryRun}
                    disabled={running}
                    onChange={(e) => toggleDryRun(e.target.checked)}
                  />
                  드라이런
                </label>
                {dryRun && (
                  <span className="badge badge--amber">실제 예약 안 함</span>
                )}
              </span>
            </div>
            {error && <div className="error-note">{error}</div>}
          </div>
        </section>

        {/* 로그 */}
        <section className="card">
          <div className="card__head">
            <span className="card__title">로그</span>
            <span className="card__hint">{logs.length} lines</span>
          </div>
          <div className="card__body card__body--flush">
            <div className="logbox" ref={logBoxRef}>
              {logs.length > 0 ? logs.join('\n') : '아직 로그가 없습니다.'}
            </div>
          </div>
        </section>
      </main>

      {/* 예약 성공 모달 */}
      {showSuccessModal && successMsg && (
        <div
          className="modal-overlay"
          role="dialog"
          aria-modal="true"
          aria-labelledby="success-title"
        >
          <div className="modal">
            <div className="modal__head">
              <span className="modal__dot" aria-hidden />
              <span className="modal__title" id="success-title">
                예약 성공
              </span>
            </div>
            <div className="modal__body">
              <div className="modal__msg">
                {successMsg.split('\n').map((line, i) =>
                  line.includes('결제기한') ? (
                    <span key={i} className="pay-line">
                      {line}
                    </span>
                  ) : (
                    <span key={i}>
                      {line}
                      {'\n'}
                    </span>
                  ),
                )}
              </div>
              <p className="modal__note">
                결제기한 내에 SRT/코레일 공식 앱에서 결제를 완료해야 예약이
                확정됩니다.
              </p>
            </div>
            <div className="modal__foot">
              <button
                className="btn btn--primary"
                onClick={() => setDismissedMsg(successMsg)}
              >
                확인
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
