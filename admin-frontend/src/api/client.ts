export const API_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api';
export const BACKEND_PUBLIC_URL = import.meta.env.VITE_BACKEND_PUBLIC_URL ?? 'http://localhost:8000';
export const TOKEN_KEY = 'fashion_admin_token';

export type Page<T> = { items: T[]; total: number; page: number; limit: number };
export type FabricStatus = 'draft' | 'published' | 'hidden' | 'archived';
export type StockStatus = 'in_stock' | 'preorder' | 'out_of_stock';
export type FabricImage = { id: string; fabric_id: string; image_url: string; image_type: 'main' | 'texture' | 'extra' | string; sort_order: number; created_at: string };
export type Fabric = {
  id: string; sku: string; name: string; category: string; composition?: string | null; color?: string | null; shade?: string | null; pattern?: string | null; texture?: string | null; density?: string | null; stretch?: string | null; opacity?: string | null; shine?: string | null; season?: string[] | null; recommended_for?: string[] | null; not_recommended_for?: string[] | null; price_per_meter?: string | number | null; currency: string; stock_status: StockStatus; stock_quantity?: string | number | null; short_description?: string | null; full_description?: string | null; description_for_gpt?: string | null; tags?: string[] | null; status: FabricStatus; images: FabricImage[]; created_at?: string; updated_at?: string;
};
export type GarmentStyle = { id: string; name: string; category: string; status: string; description?: string | null; compatible_fabric_categories?: string[] | null; base_image_url?: string | null; mask_image_url?: string | null; created_at?: string; updated_at?: string };
export type Generation = { id: string; mode: string; status: string; error_message?: string | null; created_at: string };

export class AdminApiError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message);
    this.name = 'AdminApiError';
  }
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY) ?? sessionStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
  sessionStorage.removeItem(TOKEN_KEY);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(TOKEN_KEY);
}

export function logout(): void {
  clearToken();
  window.location.hash = '#/login';
}

export function resolveImageUrl(imageUrl?: string | null): string {
  if (!imageUrl) return '';
  if (imageUrl.startsWith('/uploads')) return `${BACKEND_PUBLIC_URL}${imageUrl}`;
  return imageUrl;
}

function fallbackMessageForStatus(status: number): string {
  if (status === 400) return 'Проверьте введенные данные и повторите действие.';
  if (status === 401) return 'Сессия истекла. Войдите заново.';
  if (status === 403) return 'Недостаточно прав для выполнения действия.';
  if (status === 404) return 'Запрашиваемый объект не найден.';
  if (status === 409) return 'Такой объект уже существует. Проверьте уникальные поля.';
  if (status === 422) return 'Проверьте поля формы: часть значений заполнена некорректно.';
  if (status >= 500) return 'Сервер временно недоступен. Повторите попытку позже.';
  return 'Не удалось выполнить действие.';
}

function sanitizeErrorMessage(status: number): string {
  return fallbackMessageForStatus(status);
}

export async function apiRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (!(options.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  const token = getToken();
  if (token) headers.set('Authorization', `Bearer ${token}`);

  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, { ...options, headers });
  } catch {
    throw new AdminApiError(0, 'Не удалось подключиться к серверу. Проверьте соединение и повторите попытку.');
  }

  if (response.status === 401) {
    logout();
    throw new AdminApiError(401, fallbackMessageForStatus(401));
  }
  if (response.status === 403) {
    throw new AdminApiError(403, fallbackMessageForStatus(403));
  }
  if (!response.ok) {
    const contentType = response.headers.get('content-type') ?? '';
    if (contentType.includes('application/json')) await response.json().catch(() => null);
    else await response.text().catch(() => '');
    throw new AdminApiError(response.status, sanitizeErrorMessage(response.status));
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
