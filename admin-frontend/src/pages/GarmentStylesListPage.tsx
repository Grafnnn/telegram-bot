import { useEffect, useState } from 'react';
import { GarmentStyle } from '../api/client';
import { listGarmentStyles, setGarmentStyleStatus } from '../api/garmentStyles';
import StatusBadge from '../components/StatusBadge';

export default function GarmentStylesListPage({ navigate }: { navigate: (path: string) => void }) {
  const [items, setItems] = useState<GarmentStyle[]>([]); const [error, setError] = useState('');
  async function load() { try { setItems((await listGarmentStyles()).items); } catch (err) { setError(err instanceof Error ? err.message : 'Ошибка'); } }
  useEffect(() => { void load(); }, []);
  async function action(id: string, status: 'publish' | 'hide' | 'archive') { await setGarmentStyleStatus(id, status); await load(); }
  return <div className="space-y-4"><div className="flex justify-between"><h1 className="text-3xl font-bold">Фасоны</h1><button className="bg-slate-900 text-white" onClick={() => navigate('/garment-styles/new')}>Добавить фасон</button></div>{error && <p className="text-red-600">{error}</p>}<div className="bg-white rounded shadow divide-y">{items.map(s => <div key={s.id} className="p-4 flex justify-between"><span>{s.name} — {s.category} <StatusBadge status={s.status} /></span><span className="space-x-2"><button onClick={() => action(s.id, 'publish')}>опубликовать</button><button onClick={() => action(s.id, 'hide')}>скрыть</button><button onClick={() => action(s.id, 'archive')}>архивировать</button></span></div>)}</div></div>;
}
