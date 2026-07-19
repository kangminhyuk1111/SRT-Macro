const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';

export interface PassengerType {
  label: string;
  key: string;
  default: number;
}

export interface RailMeta {
  name: string;
  stations: string[];
  seat_types: string[];
  passenger_types: PassengerType[];
  supports_window_seat: boolean;
}

export interface Train {
  index: number;
  train_number: string;
  dep_station_name: string;
  arr_station_name: string;
  dep_time: string;
  arr_time: string;
  general_seat_state: string;
  special_seat_state: string;
}

export interface AppStatus {
  rail: string | null;
  logged_in: boolean;
  running: boolean;
  attempt: number;
  elapsed: number;
  success_message: string | null;
  train_count: number;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      /* JSON이 아닌 오류 응답은 statusText 사용 */
    }
    throw new Error(detail);
  }
  return res.json();
}

export const api = {
  meta: () => request<Record<string, RailMeta>>('/api/meta'),
  state: () => request<AppStatus>('/api/state'),
  login: (rail: string, user_id: string, password: string) =>
    request<{ message: string }>('/api/login', {
      method: 'POST',
      body: JSON.stringify({ rail, user_id, password }),
    }),
  logout: () => request<{ message: string }>('/api/logout', { method: 'POST' }),
  search: (dep: string, arr: string, date: string, time_from: string) =>
    request<{ trains: Train[] }>('/api/search', {
      method: 'POST',
      body: JSON.stringify({ dep, arr, date, time_from }),
    }),
  reserveStart: (body: {
    train_indices: number[];
    seat_type: string;
    window_seat: boolean;
    passengers: Record<string, number>;
    interval: number;
    discord_webhook: string;
  }) =>
    request<{ message: string }>('/api/reserve/start', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  reserveStop: () =>
    request<{ message: string }>('/api/reserve/stop', { method: 'POST' }),
  logs: (after: number) =>
    request<{ logs: string[]; next: number }>(`/api/logs?after=${after}`),
  clearLogs: () => request<{ message: string }>('/api/logs', { method: 'DELETE' }),
  getConfig: (rail: string) => request<Record<string, unknown>>(`/api/config/${rail}`),
  putConfig: (rail: string, cfg: Record<string, unknown>) =>
    request<{ message: string }>(`/api/config/${rail}`, {
      method: 'PUT',
      body: JSON.stringify(cfg),
    }),
};
