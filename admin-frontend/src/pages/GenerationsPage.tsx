import { useEffect, useState } from 'react';
import { Generation } from '../api/client';
import { listGenerations } from '../api/generations';
import StatusBadge from '../components/StatusBadge';

export default function GenerationsPage() {
  const [items, setItems] = useState<Generation[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listGenerations()
      .then((data) => setItems(data.items))
      .catch((err) => setError(err instanceof Error ? err.message : 'Ошибка загрузки генераций.'))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-4">
      <h1 className="text-3xl font-bold">Генерации</h1>
      {loading && <div className="rounded-xl bg-white p-6 shadow-sm">Загрузка генераций...</div>}
      {error && <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-red-700">{error}</div>}
      {!loading && !error && items.length === 0 && (
        <div className="rounded-xl bg-white p-10 text-center shadow-sm">
          <p className="text-lg font-medium">Генераций пока нет</p>
        </div>
      )}
      {!loading && items.length > 0 && (
        <div className="divide-y rounded-xl bg-white shadow-sm">
          {items.map((generation) => (
            <div className="flex flex-wrap items-center gap-2 p-4" key={generation.id}>
              <span>{generation.mode}</span>
              <StatusBadge status={generation.status} />
              {generation.error_message && <span className="text-red-600">Ошибка генерации скрыта из интерфейса.</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
