import { apiRequest, Generation, Page } from './client';

export const listGenerations = () => apiRequest<Page<Generation>>('/admin/generations');
