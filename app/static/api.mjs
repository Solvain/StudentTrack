const scoreFormatter = new Intl.NumberFormat('ru-RU', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export function formatScore(value) {
  return value === null || value === undefined ? '—' : scoreFormatter.format(value);
}

export class ApiError extends Error {
  constructor(status, detail) {
    super(typeof detail === 'string' ? detail : `HTTP ${status}`);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

export function setToken(token) {
  sessionStorage.setItem('studenttrack.token', token);
}
export function clearToken() {
  sessionStorage.removeItem('studenttrack.token');
}

export async function request(path, { method = 'GET', data, missing = false, fetcher = globalThis.fetch } = {}) {
  const init = { method, headers: { Accept: 'application/json' } };
  const token = globalThis.sessionStorage?.getItem('studenttrack.token');
  if (token && !path.startsWith('/auth/')) init.headers.Authorization = `Bearer ${token}`;
  if (data !== undefined) {
    init.headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(data);
  }

  const response = await fetcher(`/api${path}`, init);
  if (response.status === 204 || (missing && response.status === 404)) return null;
  const payload = await response.json().catch(() => null);

  if (response.status === 401 && !path.startsWith('/auth/') && typeof window !== 'undefined') {
    clearToken();
    window.location.replace('/login');
  }
  if (!response.ok) throw new ApiError(response.status, payload?.detail);
  return payload;
}
