import { useEffect, useState } from 'react';
import { GarmentStyle, resolveImageUrl } from '../api/client';
import { listGarmentStyles, setGarmentStyleStatus } from '../api/garmentStyles';
import StatusBadge from '../components/StatusBadge';

export default function GarmentStylesListPage({ navigate }: { navigate: (path: string) => void }) {
  const [items, setItems] = useState<GarmentStyle[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [actionId, setActionId] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError('');
    try {
      setItems((await listGarmentStyles()).items);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка загрузки фасонов.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);

  async function action(id: string, status: 'publish' | 'hide' | 'archive') {
    setActionId(`${status}-${id}`);
    setError('');
    try {
      await setGarmentStyleStatus(id, status);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось изменить статус фасона.');
    } finally {
      setActionId(null);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between">
        <h1 className="text-3xl font-bold">Фасоны</h1>
        <button className="rounded bg-slate-900 px-4 py-2 text-white" onClick={() => navigate('/garment-styles/new')}>Добавить фасон</button>
      </div>
      {error && <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-red-700">{error}</div>}
      {loading && <div className="rounded-xl bg-white p-6 shadow-sm">Загрузка фасонов...</div>}
      {!loading && items.length === 0 && (
        <div className="rounded-xl bg-white p-10 text-center shadow-sm">
          <p className="text-lg font-medium">Фасоны пока не добавлены</p>
          <button type="button" className="mt-4 rounded bg-slate-900 px-4 py-2 text-white" onClick={() => navigate('/garment-styles/new')}>Добавить первый фасон</button>
        </div>
      )}
      {!loading && items.length > 0 && <div className="divide-y rounded bg-white shadow">
        {items.map((style) => {
          const busy = actionId?.endsWith(style.id);
          return (
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
              <button disabled={busy} onClick={() => void action(style.id, 'publish')}>опубликовать</button>
              <button disabled={busy} onClick={() => void action(style.id, 'hide')}>скрыть</button>
              <button disabled={busy} onClick={() => void action(style.id, 'archive')}>архивировать</button>
            </div>
          </div>
          );
        })}
      </div>}
    </div>
  );
}
