import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiRequest, clearToken, getToken, setToken, TOKEN_KEY } from './client';

class MemoryStorage implements Storage {
  private values = new Map<string, string>();

  get length(): number {
    return this.values.size;
  }

  clear(): void {
    this.values.clear();
  }

  getItem(key: string): string | null {
    return this.values.get(key) ?? null;
  }

  key(index: number): string | null {
    return Array.from(this.values.keys())[index] ?? null;
  }

  removeItem(key: string): void {
    this.values.delete(key);
  }

  setItem(key: string, value: string): void {
    this.values.set(key, value);
  }
}

function jsonResponse(status: number, payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

describe('admin API client errors', () => {
  let local: MemoryStorage;
  let session: MemoryStorage;
  let location: { hash: string };

  beforeEach(() => {
    local = new MemoryStorage();
    session = new MemoryStorage();
    location = { hash: '' };
    vi.stubGlobal('localStorage', local);
    vi.stubGlobal('sessionStorage', session);
    vi.stubGlobal('window', { location });
    vi.stubGlobal('fetch', vi.fn());
  });

  it('sends the admin token without exposing it in successful responses', async () => {
    setToken('admin-secret-token');
    vi.mocked(fetch).mockResolvedValue(jsonResponse(200, { ok: true }));

    await expect(apiRequest('/health')).resolves.toEqual({ ok: true });

    const [, init] = vi.mocked(fetch).mock.calls[0];
    expect((init?.headers as Headers).get('Authorization')).toBe('Bearer admin-secret-token');
  });

  it('clears local and session tokens on 401 and redirects to login', async () => {
    setToken('admin-secret-token');
    session.setItem(TOKEN_KEY, 'stale-session-token');
    vi.mocked(fetch).mockResolvedValue(jsonResponse(401, { detail: 'Bearer admin-secret-token traceback' }));

    await expect(apiRequest('/admin/fabrics')).rejects.toThrow('Сессия истекла. Войдите заново.');

    expect(getToken()).toBeNull();
    expect(local.getItem(TOKEN_KEY)).toBeNull();
    expect(session.getItem(TOKEN_KEY)).toBeNull();
    expect(location.hash).toBe('#/login');
  });

  it('keeps the token on 403 and shows access denied', async () => {
    setToken('admin-secret-token');
    vi.mocked(fetch).mockResolvedValue(jsonResponse(403, { detail: 'not enough role' }));

    await expect(apiRequest('/admin/fabrics')).rejects.toThrow('Недостаточно прав для выполнения действия.');

    expect(getToken()).toBe('admin-secret-token');
    expect(location.hash).toBe('');
  });

  it.each<[number, string]>([
    [404, 'Запрашиваемый объект не найден.'],
    [409, 'Такой объект уже существует. Проверьте уникальные поля.'],
    [422, 'Проверьте поля формы: часть значений заполнена некорректно.'],
    [500, 'Сервер временно недоступен. Повторите попытку позже.'],
  ])('maps %s to a safe user-facing message', async (status, message) => {
    setToken('admin-secret-token');
    vi.mocked(fetch).mockResolvedValue(jsonResponse(status, { detail: 'Bearer admin-secret-token X-Bot-Token traceback' }));

    await apiRequest('/admin/fabrics').catch((error: unknown) => {
      const text = error instanceof Error ? error.message : String(error);
      expect(text).toBe(message);
      expect(text).not.toContain('admin-secret-token');
      expect(text).not.toContain('X-Bot-Token');
      expect(text).not.toContain('traceback');
    });
  });

  it('maps network errors to a friendly retry message', async () => {
    vi.mocked(fetch).mockRejectedValue(new Error('ECONNREFUSED admin-secret-token'));

    await expect(apiRequest('/admin/fabrics')).rejects.toThrow('Не удалось подключиться к серверу. Проверьте соединение и повторите попытку.');
  });

  it('clears both token stores explicitly', () => {
    local.setItem(TOKEN_KEY, 'local-token');
    session.setItem(TOKEN_KEY, 'session-token');

    clearToken();

    expect(local.getItem(TOKEN_KEY)).toBeNull();
    expect(session.getItem(TOKEN_KEY)).toBeNull();
  });
});
