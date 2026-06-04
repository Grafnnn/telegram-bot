import { apiRequest, setToken } from './client';

export async function login(email: string, password: string): Promise<void> {
  const data = await apiRequest<{ access_token: string }>('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) });
  setToken(data.access_token);
}
