import { FormEvent, useEffect, useMemo, useState } from 'react';
import { resolveImageUrl } from '../api/client';
import { archiveFabric, deleteFabric, Fabric, FabricFilters, getFabrics, hideFabric, publishFabric } from '../api/fabrics';
import StatusBadge from '../components/StatusBadge';

const STOCK_LABELS: Record<string, string> = {
  in_stock: 'В наличии',
  preorder: 'Под заказ',
  out_of_stock: 'Нет в наличии',
};

const STATUS_OPTIONS = [
  ['', 'Все статусы'],
  ['draft', 'Черновик'],
  ['published', 'Опубликовано'],
  ['hidden', 'Скрыто'],
  ['archived', 'Архив'],
];

const STOCK_OPTIONS = [
  ['', 'Любое наличие'],
  ['in_stock', 'В наличии'],
  ['preorder', 'Под заказ'],
  ['out_of_stock', 'Нет в наличии'],
];

export default function FabricsListPage({ navigate }: { navigate: (path: string) => void }) {
  const [items, setItems] = useState<Fabric[]>([]);
  const [filters, setFilters] = useState<FabricFilters>({ page: 1, limit: 30 });
  const [draftFilters, setDraftFilters] = useState<FabricFilters>({ page: 1, limit: 30 });
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(true);
  const [actionId, setActionId] = useState<string | null>(null);

  const hasFilters = useMemo(() => ['search', 'category', 'color', 'status', 'stock_status'].some((key) => Boolean(filters[key as keyof FabricFilters])), [filters]);

  async function load(nextFilters = filters) {
    setLoading(true);
    setError('');
    try {
      const data = await getFabrics(nextFilters);
      setItems(data.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка загрузки тканей.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(filters); }, [filters]);

  function submitFilters(event: FormEvent) {
    event.preventDefault();
    setFilters({ ...draftFilters, page: 1, limit: 30 });
  }

  function resetFilters() {
    const next = { page: 1, limit: 30 };
    setDraftFilters(next);
    setFilters(next);
  }

  async function runAction(id: string, action: 'publish' | 'hide' | 'archive' | 'delete') {
    if (action === 'archive' && !confirm('Архивировать ткань?')) return;
    if (action === 'delete' && !confirm('Удалить ткань без возможности восстановления?')) return;
    setActionId(`${action}-${id}`);
    setError('');
    setSuccess('');
    try {
      if (action === 'publish') await publishFabric(id);
      if (action === 'hide') await hideFabric(id);
      if (action === 'archive') await archiveFabric(id);
      if (action === 'delete') await deleteFabric(id);
      setSuccess(action === 'publish' ? 'Ткань опубликована.' : action === 'hide' ? 'Ткань скрыта.' : action === 'archive' ? 'Ткань отправлена в архив.' : 'Ткань удалена.');
      await load(filters);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось выполнить действие.');
    } finally {
      setActionId(null);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold">Ткани</h1>
          <p className="text-slate-500">Каталог тканей для админки и Telegram-бота.</p>
        </div>
        <button type="button" className="bg-slate-900 text-white" onClick={() => navigate('/fabrics/new')}>Добавить ткань</button>
      </div>

      <form className="grid gap-3 rounded-xl bg-white p-4 shadow-sm md:grid-cols-6" onSubmit={submitFilters}>
        <input placeholder="Поиск" value={draftFilters.search ?? ''} onChange={(event) => setDraftFilters({ ...draftFilters, search: event.target.value })} />
        <input placeholder="Категория" value={draftFilters.category ?? ''} onChange={(event) => setDraftFilters({ ...draftFilters, category: event.target.value })} />
        <input placeholder="Цвет" value={draftFilters.color ?? ''} onChange={(event) => setDraftFilters({ ...draftFilters, color: event.target.value })} />
        <select value={draftFilters.status ?? ''} onChange={(event) => setDraftFilters({ ...draftFilters, status: event.target.value })}>{STATUS_OPTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
        <select value={draftFilters.stock_status ?? ''} onChange={(event) => setDraftFilters({ ...draftFilters, stock_status: event.target.value })}>{STOCK_OPTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
        <div className="flex gap-2"><button className="bg-slate-900 text-white" disabled={loading}>Фильтровать</button><button type="button" className="border bg-white" onClick={resetFilters}>Сброс</button></div>
      </form>

      {error && <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-red-700">{error}</div>}
      {success && <div className="rounded-xl border border-green-200 bg-green-50 p-4 text-green-700">{success}</div>}
      {loading && <div className="rounded-xl bg-white p-6 shadow-sm">Загрузка тканей...</div>}

      {!loading && items.length === 0 && (
        <div className="rounded-xl bg-white p-10 text-center shadow-sm">
          <p className="text-lg font-medium">{hasFilters ? 'По фильтрам ничего не найдено' : 'Ткани пока не добавлены'}</p>
          <button type="button" className="mt-4 bg-slate-900 text-white" onClick={() => navigate('/fabrics/new')}>Добавить первую ткань</button>
        </div>
      )}

      {!loading && items.length > 0 && (
        <div className="overflow-x-auto rounded-xl bg-white shadow-sm">
          <table className="w-full min-w-[980px] text-left text-sm">
            <thead className="bg-slate-50 text-slate-600">
              <tr>
                <th className="p-3">Фото</th>
                <th className="p-3">Артикул</th>
                <th className="p-3">Название</th>
                <th className="p-3">Категория</th>
                <th className="p-3">Цвет</th>
                <th className="p-3">Цена</th>
                <th className="p-3">Наличие</th>
                <th className="p-3">Статус</th>
                <th className="p-3">Действия</th>
              </tr>
            </thead>
            <tbody>
              {items.map((fabric) => {
                const mainImage = fabric.images?.find((image) => image.image_type === 'main');
                const busy = actionId?.endsWith(fabric.id);
                return (
                  <tr key={fabric.id} className="border-t align-top">
                    <td className="p-3">{mainImage ? <img src={resolveImageUrl(mainImage.image_url)} alt={fabric.name} className="h-16 w-16 rounded object-cover" /> : <div className="grid h-16 w-16 place-items-center rounded bg-slate-100 text-xs text-slate-400">Нет фото</div>}</td>
                    <td className="p-3 font-mono text-xs">{fabric.sku}</td>
                    <td className="p-3 font-medium">{fabric.name}</td>
                    <td className="p-3">{fabric.category}</td>
                    <td className="p-3">{fabric.color || '—'}</td>
                    <td className="p-3">{fabric.price_per_meter ?? '—'} {fabric.currency}</td>
                    <td className="p-3">{STOCK_LABELS[fabric.stock_status] ?? fabric.stock_status}</td>
                    <td className="p-3"><StatusBadge status={fabric.status} /></td>
                    <td className="p-3">
                      <div className="flex flex-wrap gap-1">
                        <button type="button" className="border bg-white" onClick={() => navigate(`/fabrics/${fabric.id}`)}>Редактировать</button>
                        <button type="button" disabled={busy} className="border bg-white disabled:opacity-50" onClick={() => runAction(fabric.id, 'publish')}>Опубликовать</button>
                        <button type="button" disabled={busy} className="border bg-white disabled:opacity-50" onClick={() => runAction(fabric.id, 'hide')}>Скрыть</button>
                        <button type="button" disabled={busy} className="border bg-white disabled:opacity-50" onClick={() => runAction(fabric.id, 'archive')}>Архивировать</button>
                        <button type="button" disabled={busy} className="border bg-white text-red-600 disabled:opacity-50" onClick={() => runAction(fabric.id, 'delete')}>Удалить</button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
