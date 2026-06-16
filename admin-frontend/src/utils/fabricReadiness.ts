import type { FabricReadiness } from '../api/client';

const IMAGE_TYPE_LABELS: Record<string, string> = {
  main: 'main',
  texture: 'texture',
};

export type ReadinessTone = 'ready' | 'warning' | 'unknown';

export type ReadinessSummary = {
  label: string;
  detail: string;
  tone: ReadinessTone;
};

function imageTypeLabel(value?: string | null): string {
  if (!value) return 'image';
  return IMAGE_TYPE_LABELS[value] ?? value;
}

export function summarizeFabricReadiness(readiness?: FabricReadiness | null): ReadinessSummary {
  if (!readiness) {
    return {
      label: 'Готовность не проверена',
      detail: 'Сохраните карточку и обновите список.',
      tone: 'unknown',
    };
  }
  if (readiness.public_catalog_ready) {
    return {
      label: 'Готово к публикации',
      detail: readiness.try_on_ready ? 'Public catalog и try-on готовы.' : 'Public catalog готов, AI reference требует проверки.',
      tone: 'ready',
    };
  }
  if (readiness.missing_required_image_types.length > 0) {
    return {
      label: `Не готово: отсутствует ${readiness.missing_required_image_types.map(imageTypeLabel).join(', ')}`,
      detail: 'Загрузите обязательные изображения перед публикацией.',
      tone: 'warning',
    };
  }
  if (readiness.missing_upload_files.length > 0) {
    const types = Array.from(new Set(readiness.missing_upload_files.map((item) => imageTypeLabel(item.image_type))));
    return {
      label: `Файл изображения не найден: ${types.join(', ')}`,
      detail: 'Загрузите изображение заново перед публикацией.',
      tone: 'warning',
    };
  }
  return {
    label: 'Не готово к публикации',
    detail: readiness.warnings[0] ?? 'Проверьте обязательные изображения.',
    tone: 'warning',
  };
}

export function readinessClassName(tone: ReadinessTone): string {
  if (tone === 'ready') return 'bg-green-100 text-green-800';
  if (tone === 'warning') return 'bg-yellow-100 text-yellow-800';
  return 'bg-slate-100 text-slate-700';
}
