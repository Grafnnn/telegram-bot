import { apiRequest, GarmentStyle, Page } from './client';

export type GarmentStylePayload = { name?: string; category?: string; description?: string; status?: string };
export const listGarmentStyles = () => apiRequest<Page<GarmentStyle>>('/admin/garment-styles');
export const createGarmentStyle = (payload: GarmentStylePayload) => apiRequest<GarmentStyle>('/admin/garment-styles', { method: 'POST', body: JSON.stringify(payload) });
export const setGarmentStyleStatus = (id: string, action: 'publish' | 'hide' | 'archive') => apiRequest<GarmentStyle>(`/admin/garment-styles/${id}/${action}`, { method: 'POST' });
