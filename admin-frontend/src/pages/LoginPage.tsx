import { FormEvent, useState } from 'react';
import { login } from '../api/auth';

export default function LoginPage({ navigate }: { navigate: (path: string) => void }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  async function submit(event: FormEvent) { event.preventDefault(); setLoading(true); setError(''); try { await login(email, password); navigate('/'); } catch (err) { setError(err instanceof Error ? err.message : 'Ошибка входа'); } finally { setLoading(false); } }
  return <div className="min-h-screen grid place-items-center"><form onSubmit={submit} className="bg-white p-8 rounded-xl shadow w-96 space-y-4"><h1 className="text-2xl font-bold">Вход в админку</h1>{error && <p className="text-red-600">{error}</p>}<input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="Email" /><input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="Пароль" /><button disabled={loading} className="bg-slate-900 text-white w-full">{loading ? 'Входим...' : 'Войти'}</button></form></div>;
}
