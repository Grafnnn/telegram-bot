const STATUS_LABELS: Record<string, string> = {
  completed: 'Готово',
  draft: 'Черновик',
  archived: 'Архив',
  failed: 'Ошибка',
  hidden: 'Скрыто',
  out_of_stock: 'Нет в наличии',
  pending: 'В очереди',
  processing: 'В работе',
  published: 'Опубликовано',
};

const STATUS_COLORS: Record<string, string> = {
  completed: 'bg-green-100 text-green-800',
  published: 'bg-green-100 text-green-800',
  draft: 'bg-slate-100 text-slate-800',
  hidden: 'bg-yellow-100 text-yellow-800',
  archived: 'bg-red-100 text-red-800',
  out_of_stock: 'bg-red-100 text-red-800',
  failed: 'bg-red-100 text-red-800',
  pending: 'bg-blue-100 text-blue-800',
  processing: 'bg-blue-100 text-blue-800',
};

export const UNKNOWN_STATUS_LABEL = 'Неизвестный статус';

export function statusLabel(status: string): string {
  return STATUS_LABELS[status] ?? UNKNOWN_STATUS_LABEL;
}

export function statusClassName(status: string): string {
  return STATUS_COLORS[status] ?? 'bg-slate-100 text-slate-800';
}

export default function StatusBadge({ status }: { status: string }) {
  return <span className={`inline-flex px-2 py-1 rounded-full text-xs font-medium ${statusClassName(status)}`}>{statusLabel(status)}</span>;
}
