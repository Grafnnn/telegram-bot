import { useEffect, useState } from 'react';
import { GarmentStyle, resolveImageUrl } from '../api/client';
import { listGarmentStyles, setGarmentStyleStatus } from '../api/garmentStyles';
import StatusBadge from '../components/StatusBadge';

export default function GarmentStylesListPage({ navigate }: { navigate: (path: string) => void }) {
  const [items, setItems] = useState<GarmentStyle[]>([]);
  const [error, setError] = useState('');

  async function load() {
    try { setItems((await listGarmentStyles()).items); } catch (err) { setError(err instanceof Error ? err.message : 'Ошибка'); }
  }

  useEffect(() => { void load(); }, []);

  async function action(id: string, status: 'publish' | 'hide' | 'archive') {
    await setGarmentStyleStatus(id, status);
    await load();
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between">
        <h1 className="text-3xl font-bold">Фасоны</h1>
        <button className="rounded bg-slate-900 px-4 py-2 text-white" onClick={() => navigate('/garment-styles/new')}>Добавить фасон</button>
      </div>
      {error && <p className="text-red-600">{error}</p>}
      <div className="divide-y rounded bg-white shadow">
        {items.map((style) => (
          <div key={style.id} className="grid gap-4 p-4 md:grid-cols-[120px_1fr_auto]">
            <div className="h-24 rounded bg-slate-100">
              {style.base_image_url && <img src={resolveImageUrl(style.base_image_url)} alt={style.name} className="h-24 w-full rounded object-cover" />}
            </div>
            <div>
              <button className="text-left text-lg font-semibold hover:underline" onClick={() => navigate(`/garment-styles/${style.id}`)}>{style.name}</button>
              <p className="text-slate-500">{style.category}</p>
              <StatusBadge status={style.status} />
              {style.description && <p className="mt-2 text-sm text-slate-600">{style.description}</p>}
            </div>
            <div className="flex flex-wrap items-start gap-2">
              <button onClick={() => navigate(`/garment-styles/${style.id}`)}>редактировать</button>
              <button onClick={() => void action(style.id, 'publish')}>опубликовать</button>
              <button onClick={() => void action(style.id, 'hide')}>скрыть</button>
              <button onClick={() => void action(style.id, 'archive')}>архивировать</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
