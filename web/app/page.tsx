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

  const railMeta = meta?.[rail];
  const loggedIn = Boolean(status?.logged_in && status.rail === rail);
  const running = Boolean(status?.running);

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

  // 상태 폴링
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

  // 로그 폴링
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

  if (!meta) {
    return (
      <main className="container">
        <div className="header">
          <h1>기차 예약 매크로</h1>
        </div>
        <div className="panel">
          {error || '불러오는 중...'}
        </div>
      </main>
    );
  }

  return (
    <main className="container">
      <div className="header">
        <h1>기차 예약 매크로</h1>
        <div className="rail-tabs">
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
        </div>
      </div>

      {status?.success_message && (
        <div className="success-banner">{status.success_message}</div>
      )}

      <div className="panel">
        <h2>로그인 — {railMeta?.name}</h2>
        {loggedIn ? (
          <div className="row">
            <span className="badge">로그인됨 ({userId})</span>
            <button className="btn secondary" onClick={doLogout} disabled={running}>
              로그아웃
            </button>
          </div>
        ) : (
          <div className="row">
            <div className="field">
              <label>아이디 (멤버십번호/이메일/전화번호)</label>
              <input
                value={userId}
                onChange={(e) => setUserId(e.target.value)}
                style={{ width: 220 }}
              />
            </div>
            <div className="field">
              <label>비밀번호</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && doLogin()}
                style={{ width: 180 }}
              />
            </div>
            <button className="btn" onClick={doLogin} disabled={loggingIn}>
              {loggingIn ? <span className="spin" /> : '로그인'}
            </button>
          </div>
        )}
      </div>

      <div className="panel">
        <h2>열차 검색</h2>
        <div className="row">
          <div className="field">
            <label>출발역</label>
            <select value={dep} onChange={(e) => setDep(e.target.value)}>
              {railMeta?.stations.map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>도착역</label>
            <select value={arr} onChange={(e) => setArr(e.target.value)}>
              {railMeta?.stations.map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>날짜</label>
            <input
              type="date"
              value={date}
              min={todayISO()}
              onChange={(e) => setDate(e.target.value)}
            />
          </div>
          <div className="field">
            <label>출발 시각</label>
            <select value={timeFrom} onChange={(e) => setTimeFrom(e.target.value)}>
              {HOURS.map((h) => (
                <option key={h} value={h}>
                  {h}시
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>~ 까지</label>
            <select value={timeTo} onChange={(e) => setTimeTo(e.target.value)}>
              {HOURS.map((h) => (
                <option key={h} value={h}>
                  {h}시
                </option>
              ))}
            </select>
          </div>
          <button
            className="btn"
            onClick={doSearch}
            disabled={!loggedIn || searching || running}
          >
            {searching ? <span className="spin" /> : '검색'}
          </button>
        </div>
      </div>

      {trains.length > 0 && (
        <div className="panel">
          <h2>
            열차 선택 ({selected.size}/{trains.length})
          </h2>
          <table className="train-table">
            <thead>
              <tr>
                <th>
                  <input
                    type="checkbox"
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
                    {railMeta?.name} {t.train_number}
                  </td>
                  <td>
                    {t.dep_station_name} → {t.arr_station_name}
                  </td>
                  <td>{fmtTime(t.dep_time)}</td>
                  <td>{fmtTime(t.arr_time)}</td>
                  <td
                    className={
                      t.general_seat_state.includes('가능') ? 'seat-ok' : 'seat-soldout'
                    }
                  >
                    {t.general_seat_state}
                  </td>
                  <td
                    className={
                      t.special_seat_state.includes('가능') ? 'seat-ok' : 'seat-soldout'
                    }
                  >
                    {t.special_seat_state}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="panel">
        <h2>예매 옵션</h2>
        <div className="row" style={{ marginBottom: 12 }}>
          <div className="field">
            <label>좌석 유형</label>
            <select value={seatType} onChange={(e) => setSeatType(e.target.value)}>
              {railMeta?.seat_types.map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </div>
          {railMeta?.supports_window_seat && (
            <div className="field">
              <label>창가 우선</label>
              <input
                type="checkbox"
                checked={windowSeat}
                onChange={(e) => setWindowSeat(e.target.checked)}
                style={{ marginTop: 8 }}
              />
            </div>
          )}
          {railMeta?.passenger_types.map((pt) => (
            <div className="field" key={pt.key}>
              <label>{pt.label}</label>
              <input
                type="number"
                min={0}
                max={9}
                value={passengers[pt.key] ?? 0}
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
            <label>재시도 간격(초)</label>
            <input
              type="number"
              step={0.1}
              min={0.1}
              value={interval_}
              onChange={(e) => setInterval_(Number(e.target.value) || 0.8)}
              style={{ width: 90 }}
            />
          </div>
          <div className="field" style={{ flex: 1, minWidth: 220 }}>
            <label>디스코드 웹훅 (선택)</label>
            <input
              value={webhook}
              onChange={(e) => setWebhook(e.target.value)}
              placeholder="https://discord.com/api/webhooks/..."
            />
          </div>
        </div>
        <div className="status-bar">
          {running ? (
            <button className="btn danger" onClick={doStop}>
              예매 중지
            </button>
          ) : (
            <button
              className="btn"
              onClick={doStart}
              disabled={!loggedIn || selected.size === 0}
            >
              예매 시작 ({selected.size}개 열차)
            </button>
          )}
          {running && (
            <>
              <span className="stat">
                시도 <b>{status?.attempt ?? 0}</b>회
              </span>
              <span className="stat">
                경과 <b>{fmtElapsed(status?.elapsed ?? 0)}</b>
              </span>
              <span className="spin" style={{ borderTopColor: 'var(--accent)' }} />
            </>
          )}
        </div>
        {error && <div className="error-text">{error}</div>}
      </div>

      <div className="panel">
        <h2>로그</h2>
        <div className="log-box" ref={logBoxRef}>
          {logs.length > 0 ? logs.join('\n') : '아직 로그가 없습니다.'}
        </div>
      </div>
    </main>
  );
}
