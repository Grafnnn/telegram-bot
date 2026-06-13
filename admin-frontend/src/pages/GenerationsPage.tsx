import { useEffect, useState } from 'react';
import { resolveImageUrl } from '../api/client';
import type { Generation } from '../api/client';
import { listGenerations } from '../api/generations';
import StatusBadge from '../components/StatusBadge';

export function generationModeLabel(mode: string): string {
  if (mode === 'user_photo') return 'Примерка по фото';
  if (mode === 'catalog_style') return 'Каталог + фасон';
  return mode;
}

export function generationFabricLabel(generation: Generation): string {
  if (generation.fabric) return `${generation.fabric.name} (${generation.fabric.sku})`;
  return generation.fabric_id ? `Ткань ${generation.fabric_id}` : 'Ткань не указана';
}

export function generationUserLabel(generation: Generation): string {
  if (generation.telegram_user?.username) return `@${generation.telegram_user.username}`;
  if (generation.telegram_user?.telegram_id) return `Telegram ID ${generation.telegram_user.telegram_id}`;
  return generation.telegram_user_id ? `Пользователь ${generation.telegram_user_id}` : 'Пользователь не указан';
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('ru-RU', {
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    month: '2-digit',
    year: '2-digit',
  });
}

function shortId(value: string): string {
  return value.slice(0, 8);
}

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
      <div>
        <h1 className="text-3xl font-bold">Генерации</h1>
        <p className="mt-1 text-sm text-slate-500">История AI-примерок и результатов, отправленных ботом.</p>
      </div>
      {loading && <div className="rounded-xl bg-white p-6 shadow-sm">Загрузка генераций...</div>}
      {error && <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-red-700">{error}</div>}
      {!loading && !error && items.length === 0 && (
        <div className="rounded-xl bg-white p-10 text-center shadow-sm">
          <p className="text-lg font-medium">Генераций пока нет</p>
        </div>
      )}
      {!loading && items.length > 0 && (
        <div className="divide-y rounded-xl bg-white shadow-sm">
          {items.map((generation) => {
            const resultUrl = resolveImageUrl(generation.result_image_url);
            return (
              <article className="grid gap-4 p-4 md:grid-cols-[112px_1fr_auto]" key={generation.id}>
                <div className="flex h-28 w-28 items-center justify-center overflow-hidden rounded-lg border border-slate-200 bg-slate-50">
                  {resultUrl ? (
                    <img className="h-full w-full object-cover" src={resultUrl} alt="Результат генерации" />
                  ) : (
                    <span className="px-3 text-center text-xs text-slate-500">Нет результата</span>
                  )}
                </div>
                <div className="min-w-0 space-y-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold text-slate-900">{generationModeLabel(generation.mode)}</span>
                    <StatusBadge status={generation.status} />
                    <span className="text-xs text-slate-500">#{shortId(generation.id)}</span>
                  </div>
                  <div className="grid gap-1 text-sm text-slate-700 sm:grid-cols-2">
                    <div>
                      <span className="text-slate-500">Ткань: </span>
                      <span className="font-medium">{generationFabricLabel(generation)}</span>
                    </div>
                    {generation.garment_style && (
                      <div>
                        <span className="text-slate-500">Фасон: </span>
                        <span className="font-medium">{generation.garment_style.name}</span>
                      </div>
                    )}
                    <div>
                      <span className="text-slate-500">Пользователь: </span>
                      <span>{generationUserLabel(generation)}</span>
                    </div>
                    <div>
                      <span className="text-slate-500">Создано: </span>
                      <span>{formatDate(generation.created_at)}</span>
                    </div>
                  </div>
                  {generation.user_photo_url && (
                    <p className="text-xs text-slate-500">Фото пользователя сохранено для аудита результата.</p>
                  )}
                  {generation.error_message && (
                    <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">Ошибка генерации скрыта из интерфейса.</p>
                  )}
                </div>
                <div className="flex items-start justify-end">
                  {resultUrl && (
                    <a
                      className="rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                      href={resultUrl}
                      rel="noreferrer"
                      target="_blank"
                    >
                      Открыть
                    </a>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}
