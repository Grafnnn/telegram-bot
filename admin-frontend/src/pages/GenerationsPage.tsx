import { useEffect, useState } from 'react';
import { Generation } from '../api/client';
import { listGenerations } from '../api/generations';
import StatusBadge from '../components/StatusBadge';

export default function GenerationsPage() {
  const [items, setItems] = useState<Generation[]>([]); const [error, setError] = useState(''); const [loading, setLoading] = useState(true);
  useEffect(() => { listGenerations().then(data => setItems(data.items)).catch(err => setError(err instanceof Error ? err.message : 'Ошибка')).finally(() => setLoading(false)); }, []);
  return <div className="space-y-4"><h1 className="text-3xl font-bold">Генерации</h1>{loading && <p>Загрузка...</p>}{error && <p className="text-red-600">{error}</p>}<div className="bg-white rounded shadow divide-y">{items.map(g => <div className="p-4" key={g.id}>{g.mode} — <StatusBadge status={g.status} /> {g.error_message && <span className="text-red-600">{g.error_message}</span>}</div>)}</div></div>;
}
