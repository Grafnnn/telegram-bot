import { apiRequest, GarmentStyle, Page } from './client';

export type GarmentStylePayload = {
  name?: string;
  category?: string;
  description?: string | null;
  compatible_fabric_categories?: string[] | null;
  status?: string;
  base_image_url?: string | null;
  mask_image_url?: string | null;
};

export const listGarmentStyles = () => apiRequest<Page<GarmentStyle>>('/admin/garment-styles');
export const getGarmentStyle = (id: string) => apiRequest<GarmentStyle>(`/admin/garment-styles/${id}`);
export const createGarmentStyle = (payload: GarmentStylePayload) => apiRequest<GarmentStyle>('/admin/garment-styles', { method: 'POST', body: JSON.stringify(payload) });
export const updateGarmentStyle = (id: string, payload: GarmentStylePayload) => apiRequest<GarmentStyle>(`/admin/garment-styles/${id}`, { method: 'PATCH', body: JSON.stringify(payload) });
export const publishGarmentStyle = (id: string) => apiRequest<GarmentStyle>(`/admin/garment-styles/${id}/publish`, { method: 'POST' });
export const hideGarmentStyle = (id: string) => apiRequest<GarmentStyle>(`/admin/garment-styles/${id}/hide`, { method: 'POST' });
export const archiveGarmentStyle = (id: string) => apiRequest<GarmentStyle>(`/admin/garment-styles/${id}/archive`, { method: 'POST' });
export const setGarmentStyleStatus = (id: string, action: 'publish' | 'hide' | 'archive') => ({ publish: publishGarmentStyle, hide: hideGarmentStyle, archive: archiveGarmentStyle }[action])(id);

export function uploadGarmentStyleImage(id: string, file: File, imageType: 'base' | 'mask') {
  const data = new FormData();
  data.append('file', file);
  data.append('image_type', imageType);
  return apiRequest<GarmentStyle>(`/admin/garment-styles/${id}/images`, { method: 'POST', body: data });
}
