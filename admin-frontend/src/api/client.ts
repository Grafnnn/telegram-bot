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
export type GarmentStyle = { id: string; name: string; category: string; status: string; description?: string | null };
export type Generation = { id: string; mode: string; status: string; error_message?: string | null; created_at: string };

export function getToken(): string | null { return localStorage.getItem(TOKEN_KEY); }
export function setToken(token: string): void { localStorage.setItem(TOKEN_KEY, token); }
export function logout(): void { localStorage.removeItem(TOKEN_KEY); window.location.hash = '#/login'; }

export function resolveImageUrl(imageUrl?: string | null): string {
  if (!imageUrl) return '';
  if (imageUrl.startsWith('/uploads')) return `${BACKEND_PUBLIC_URL}${imageUrl}`;
  return imageUrl;
}

function extractErrorMessage(payload: unknown, fallback: string): string {
  if (typeof payload === 'string') return payload;
  if (payload && typeof payload === 'object') {
    const record = payload as Record<string, unknown>;
    if (typeof record.detail === 'string') return record.detail;
    if (Array.isArray(record.detail)) return record.detail.map((item) => JSON.stringify(item)).join('\n');
    if (typeof record.error === 'string') return record.error;
    if (typeof record.message === 'string') return record.message;
  }
  return fallback;
}

export async function apiRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (!(options.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  const token = getToken();
  if (token) headers.set('Authorization', `Bearer ${token}`);
  const response = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (response.status === 401) { logout(); throw new Error('Сессия истекла. Войдите заново.'); }
  if (!response.ok) {
    const contentType = response.headers.get('content-type') ?? '';
    const payload = contentType.includes('application/json') ? await response.json() : await response.text();
    throw new Error(extractErrorMessage(payload, 'Ошибка API'));
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
