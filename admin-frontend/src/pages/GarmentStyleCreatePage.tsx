import { FormEvent, useState } from 'react';
import { createGarmentStyle } from '../api/garmentStyles';

export default function GarmentStyleCreatePage({ navigate }: { navigate: (path: string) => void }) {
  const [form, setForm] = useState({ name: '', category: '', description: '' }); const [error, setError] = useState('');
  async function submit(e: FormEvent) { e.preventDefault(); try { await createGarmentStyle(form); navigate('/garment-styles'); } catch (err) { setError(err instanceof Error ? err.message : 'Ошибка'); } }
  return <form onSubmit={submit} className="space-y-4 max-w-xl"><h1 className="text-3xl font-bold">Добавить фасон</h1>{error && <p className="text-red-600">{error}</p>}<input required placeholder="Название" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} /><input required placeholder="Категория" value={form.category} onChange={e => setForm({ ...form, category: e.target.value })} /><textarea placeholder="Описание" value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} /><button className="bg-slate-900 text-white">Создать</button></form>;
}
