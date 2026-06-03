import { apiRequest, Fabric, FabricImage, FabricStatus, Page, StockStatus } from './client';

export type { Fabric, FabricImage, FabricStatus, StockStatus } from './client';

export type FabricPayload = {
  sku?: string;
  name?: string;
  category?: string;
  composition?: string | null;
  color?: string | null;
  shade?: string | null;
  pattern?: string | null;
  texture?: string | null;
  density?: string | null;
  stretch?: string | null;
  opacity?: string | null;
  shine?: string | null;
  season?: string[] | null;
  recommended_for?: string[] | null;
  not_recommended_for?: string[] | null;
  price_per_meter?: number | null;
  currency?: string;
  stock_status?: StockStatus;
  stock_quantity?: number | null;
  short_description?: string | null;
  full_description?: string | null;
  description_for_gpt?: string | null;
  tags?: string[] | null;
  status?: FabricStatus;
  images?: FabricImage[];
  has_main_image?: boolean;
  has_texture_image?: boolean;
};

export type FabricFilters = Partial<Record<'search' | 'category' | 'color' | 'status' | 'stock_status', string>> & { page?: number; limit?: number };

export type AIGeneratedDescription = {
  ok?: boolean;
  error?: string;
  short_description?: string;
  full_description?: string;
  description_for_gpt?: string;
  tags?: string[];
  recommended_for?: string[];
  not_recommended_for?: string[];
};

export type CardCheckResult = {
  ok?: boolean;
  is_ready: boolean;
  missing_fields: string[];
  recommendations: string[];
  message: string;
};

function query(params?: FabricFilters): string {
  const search = new URLSearchParams();
  Object.entries(params ?? {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && String(value).trim() !== '') search.set(key, String(value));
  });
  const qs = search.toString();
  return qs ? `?${qs}` : '';
}

export const getFabrics = (params?: FabricFilters) => apiRequest<Page<Fabric>>(`/admin/fabrics${query(params)}`);
export const listFabrics = getFabrics;
export const getFabric = (id: string) => apiRequest<Fabric>(`/admin/fabrics/${id}`);
export const createFabric = (data: FabricPayload) => apiRequest<Fabric>('/admin/fabrics', { method: 'POST', body: JSON.stringify(data) });
export const updateFabric = (id: string, data: FabricPayload) => apiRequest<Fabric>(`/admin/fabrics/${id}`, { method: 'PATCH', body: JSON.stringify(data) });
export const deleteFabric = (id: string) => apiRequest<void>(`/admin/fabrics/${id}`, { method: 'DELETE' });
export const publishFabric = (id: string) => apiRequest<Fabric>(`/admin/fabrics/${id}/publish`, { method: 'POST' });
export const hideFabric = (id: string) => apiRequest<Fabric>(`/admin/fabrics/${id}/hide`, { method: 'POST' });
export const archiveFabric = (id: string) => apiRequest<Fabric>(`/admin/fabrics/${id}/archive`, { method: 'POST' });
export const setFabricStatus = (id: string, action: 'publish' | 'hide' | 'archive') => ({ publish: publishFabric, hide: hideFabric, archive: archiveFabric }[action])(id);

export function uploadFabricImage(id: string, file: File, imageType: 'main' | 'texture' | 'extra', sortOrder = 0) {
  const data = new FormData();
  data.append('file', file);
  data.append('image_type', imageType);
  data.append('sort_order', String(sortOrder));
  return apiRequest<FabricImage>(`/admin/fabrics/${id}/images`, { method: 'POST', body: data });
}

export const deleteFabricImage = (fabricId: string, imageId: string) => apiRequest<void>(`/admin/fabrics/${fabricId}/images/${imageId}`, { method: 'DELETE' });
export const generateFabricDescription = (data: FabricPayload) => apiRequest<AIGeneratedDescription>('/admin/fabrics/ai/generate-description', { method: 'POST', body: JSON.stringify({ fabric_data: data }) });
export const checkFabricCard = (data: FabricPayload) => apiRequest<CardCheckResult>('/admin/fabrics/ai/check-card', { method: 'POST', body: JSON.stringify({ fabric_data: data }) });
