import { useEffect, useState } from 'react';
import { GarmentStyle } from '../api/client';
import { archiveGarmentStyle, getGarmentStyle, hideGarmentStyle, publishGarmentStyle } from '../api/garmentStyles';
import GarmentStyleForm from '../components/GarmentStyleForm';
import StatusBadge from '../components/StatusBadge';

export default function GarmentStyleEditPage({ id, navigate }: { id: string; navigate: (path: string) => void }) {
  const [style, setStyle] = useState<GarmentStyle | null>(null);
  const [error, setError] = useState('');

  async function load() {
    try { setStyle(await getGarmentStyle(id)); } catch (err) { setError(err instanceof Error ? err.message : 'Ошибка загрузки фасона'); }
  }

  useEffect(() => { void load(); }, [id]);

  async function statusAction(action: 'publish' | 'hide' | 'archive') {
    try {
      const next = action === 'publish' ? await publishGarmentStyle(id) : action === 'hide' ? await hideGarmentStyle(id) : await archiveGarmentStyle(id);
      setStyle(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка изменения статуса');
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <button className="mb-3 text-sm text-slate-500 hover:underline" onClick={() => navigate('/garment-styles')}>← К списку фасонов</button>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-3xl font-bold">Редактировать фасон</h1>
          {style && <StatusBadge status={style.status} />}
        </div>
      </div>
      {error && <p className="rounded bg-red-50 p-3 text-red-700">{error}</p>}
      {style && (
        <>
          <div className="flex flex-wrap gap-2">
            <button className="rounded bg-emerald-600 px-3 py-2 text-white" onClick={() => void statusAction('publish')}>Опубликовать</button>
            <button className="rounded bg-amber-600 px-3 py-2 text-white" onClick={() => void statusAction('hide')}>Скрыть</button>
            <button className="rounded bg-slate-600 px-3 py-2 text-white" onClick={() => void statusAction('archive')}>Архивировать</button>
          </div>
          <GarmentStyleForm mode="edit" initialStyle={style} onSaved={() => void load()} />
        </>
      )}
    </div>
  );
}
