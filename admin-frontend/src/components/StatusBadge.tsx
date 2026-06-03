const STATUS_LABELS: Record<string, string> = {
  draft: 'Черновик',
  published: 'Опубликовано',
  hidden: 'Скрыто',
  out_of_stock: 'Нет в наличии',
  archived: 'Архив',
  failed: 'Ошибка',
  pending: 'В очереди',
};

const STATUS_COLORS: Record<string, string> = {
  published: 'bg-green-100 text-green-800',
  draft: 'bg-slate-100 text-slate-800',
  hidden: 'bg-yellow-100 text-yellow-800',
  archived: 'bg-red-100 text-red-800',
  out_of_stock: 'bg-red-100 text-red-800',
  failed: 'bg-red-100 text-red-800',
  pending: 'bg-blue-100 text-blue-800',
};

export default function StatusBadge({ status }: { status: string }) {
  return <span className={`inline-flex px-2 py-1 rounded-full text-xs font-medium ${STATUS_COLORS[status] ?? 'bg-slate-100 text-slate-800'}`}>{STATUS_LABELS[status] ?? status}</span>;
}
