import { ChangeEvent, useMemo, useState } from 'react';
import { createFabric, getFabrics } from '../api/fabrics';
import {
  buildCorrectedApprovedJson,
  buildDraftFabricPayload,
  EXISTING_SKU_ERROR,
  FabricImportRow,
  IMPORT_STOCK_STATUS_VALUES,
  normalizeSkuKey,
  parseFabricImportJson,
  validateFabricImportRows,
} from '../utils/fabricImportReview';

type ImportResult = {
  created: number;
  skipped: number;
  rows: Array<{ sku: string; status: 'created' | 'skipped' | 'error'; message: string; id?: string }>;
};

const STOCK_LABELS: Record<string, string> = {
  in_stock: 'В наличии',
  preorder: 'Под заказ',
  out_of_stock: 'Нет в наличии',
  unknown: 'Нужно выбрать',
  '': 'Нужно выбрать',
};

const SKU_PREFLIGHT_PAGE_LIMIT = 100;

function errorSummary(rows: FabricImportRow[]): string {
  const invalid = rows.filter((row) => row.errors.length > 0).length;
  const warnings = rows.filter((row) => row.warnings.length > 0).length;
  return `Строк: ${rows.length}. Ошибки: ${invalid}. Предупреждения: ${warnings}.`;
}

function downloadText(filename: string, text: string) {
  const blob = new Blob([text], { type: 'application/json;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

async function loadExistingSkuKeys(): Promise<Set<string>> {
  const skuKeys = new Set<string>();
  let page = 1;
  while (true) {
    const data = await getFabrics({ page, limit: SKU_PREFLIGHT_PAGE_LIMIT });
    data.items.forEach((fabric) => {
      const key = normalizeSkuKey(fabric.sku);
      if (key) skuKeys.add(key);
    });
    if (data.items.length === 0 || page * data.limit >= data.total) break;
    page += 1;
  }
  return skuKeys;
}

export default function FabricImportReviewPage({ navigate }: { navigate: (path: string) => void }) {
  const [sourceText, setSourceText] = useState('');
  const [rows, setRows] = useState<FabricImportRow[]>([]);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [result, setResult] = useState<ImportResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [importConfirmed, setImportConfirmed] = useState(false);
  const [existingSkuKeys, setExistingSkuKeys] = useState<Set<string>>(() => new Set());
  const [skuCheckLoading, setSkuCheckLoading] = useState(false);
  const [skuCheckError, setSkuCheckError] = useState('');

  const selectedRows = useMemo(() => rows.filter((row) => row.selected), [rows]);
  const importableRows = useMemo(() => selectedRows.filter((row) => row.errors.length === 0), [selectedRows]);
  const hasRows = rows.length > 0;
  const hasSelectedInvalidRows = selectedRows.some((row) => row.errors.length > 0);
  const importBlockedBySkuCheck = skuCheckLoading || Boolean(skuCheckError);
  const hasExistingSkuConflicts = rows.some((row) => row.errors.includes(EXISTING_SKU_ERROR));

  function applyRows(nextRows: FabricImportRow[], skuKeys = existingSkuKeys) {
    setRows(validateFabricImportRows(nextRows, { existingSkuKeys: skuKeys }));
    setImportConfirmed(false);
    setResult(null);
    setSuccess('');
  }

  async function parseInput(text = sourceText) {
    setError('');
    setResult(null);
    setImportConfirmed(false);
    setSkuCheckError('');
    let parsedRows: FabricImportRow[];
    try {
      parsedRows = parseFabricImportJson(text);
    } catch (err) {
      setRows([]);
      setSuccess('');
      setError(err instanceof Error ? err.message : 'Не удалось прочитать JSON.');
      return;
    }

    setRows(parsedRows);
    setSuccess(errorSummary(parsedRows));
    setSkuCheckLoading(true);
    try {
      const nextSkuKeys = await loadExistingSkuKeys();
      const checkedRows = validateFabricImportRows(parsedRows, { existingSkuKeys: nextSkuKeys });
      setExistingSkuKeys(nextSkuKeys);
      setRows(checkedRows);
      setSuccess(errorSummary(checkedRows));
    } catch {
      setSkuCheckError('Не удалось проверить существующие SKU. Импорт временно заблокирован до повторной проверки.');
      setSuccess('');
    } finally {
      setSkuCheckLoading(false);
    }
  }

  async function readFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setError('');
    setImportConfirmed(false);
    const text = await file.text();
    setSourceText(text);
    void parseInput(text);
  }

  async function retrySkuPreflight() {
    if (!hasRows) return;
    setError('');
    setSkuCheckError('');
    setSkuCheckLoading(true);
    try {
      const nextSkuKeys = await loadExistingSkuKeys();
      const checkedRows = validateFabricImportRows(rows, { existingSkuKeys: nextSkuKeys });
      setExistingSkuKeys(nextSkuKeys);
      setRows(checkedRows);
      setSuccess(errorSummary(checkedRows));
      setResult(null);
      setImportConfirmed(false);
    } catch {
      setSkuCheckError('Не удалось проверить существующие SKU. Импорт временно заблокирован до повторной проверки.');
      setSuccess('');
    } finally {
      setSkuCheckLoading(false);
    }
  }

  function updateRow<K extends keyof FabricImportRow>(id: string, field: K, value: FabricImportRow[K]) {
    applyRows(rows.map((row) => (row.id === id ? { ...row, [field]: value } : row)));
  }

  function toggleAll(checked: boolean) {
    applyRows(rows.map((row) => ({ ...row, selected: checked })));
  }

  async function importSelected() {
    setError('');
    setSuccess('');
    setResult(null);
    if (importableRows.length === 0) {
      setError('Нет выбранных валидных строк для импорта.');
      return;
    }
    if (hasSelectedInvalidRows) {
      setError('Исправьте ошибки в выбранных строках перед импортом.');
      return;
    }
    if (skuCheckLoading) {
      setError('Дождитесь завершения проверки SKU в базе.');
      return;
    }
    if (skuCheckError) {
      setError(skuCheckError);
      return;
    }
    if (!importConfirmed) {
      setError('Подтвердите создание выбранных строк как черновиков перед импортом.');
      return;
    }
    setBusy(true);
    const nextResult: ImportResult = { created: 0, skipped: 0, rows: [] };
    for (const row of importableRows) {
      try {
        const created = await createFabric(buildDraftFabricPayload(row));
        nextResult.created += 1;
        nextResult.rows.push({ sku: row.sku, status: 'created', message: 'Создан черновик.', id: created.id });
      } catch (err) {
        nextResult.skipped += 1;
        nextResult.rows.push({ sku: row.sku || `row ${row.sourceIndex + 1}`, status: 'error', message: err instanceof Error ? err.message : 'Не удалось импортировать строку.' });
      }
    }
    setResult(nextResult);
    setSuccess(`Импорт завершён. Создано: ${nextResult.created}. Ошибок/пропусков: ${nextResult.skipped}.`);
    setImportConfirmed(false);
    setBusy(false);
  }

  function clearAll() {
    setRows([]);
    setSourceText('');
    setError('');
    setSuccess('');
    setResult(null);
    setImportConfirmed(false);
    setSkuCheckError('');
    setSkuCheckLoading(false);
  }

  function downloadCorrectedJson() {
    downloadText('fabrics_approved_draft.json', buildCorrectedApprovedJson(rows));
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <button type="button" className="mb-3 text-sm text-slate-500 hover:underline" onClick={() => navigate('/fabrics')}>← К списку тканей</button>
          <h1 className="text-3xl font-bold">Импорт тканей</h1>
          <p className="text-slate-500">Проверьте preview/approved JSON, исправьте поля и импортируйте выбранные строки только как черновики.</p>
        </div>
        <div className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800">
          Статус импорта фиксирован: <b>draft</b>
        </div>
      </div>

      <section className="space-y-4 rounded-xl bg-white p-6 shadow-sm">
        <h2 className="text-xl font-semibold">Источник JSON</h2>
        <div className="grid gap-4 md:grid-cols-2">
          <label>
            Файл preview/approved JSON
            <input type="file" accept="application/json,.json" onChange={readFile} />
          </label>
          <div className="text-sm text-slate-600">
            Поддерживаются форматы <code>{'{ "items": [...] }'}</code> и прямой массив. Строки читаются из <code>normalized</code>, <code>raw</code> или плоского объекта.
          </div>
        </div>
        <label>
          Вставить JSON вручную
          <textarea
            rows={8}
            value={sourceText}
            onChange={(event) => {
              setSourceText(event.target.value);
              setImportConfirmed(false);
            }}
            placeholder='{"items":[{"normalized":{"sku":"...","name":"...","category":"...","stock_status":"preorder"}}]}'
          />
        </label>
        <div className="flex flex-wrap gap-3">
          <button type="button" className="bg-slate-900 text-white" onClick={() => void parseInput()} disabled={!sourceText.trim() || busy || skuCheckLoading}>Validate</button>
          <button type="button" className="border bg-white" onClick={downloadCorrectedJson} disabled={!hasRows || busy || importBlockedBySkuCheck}>Download corrected approved JSON</button>
          <button type="button" className="border bg-white" onClick={clearAll} disabled={busy}>Clear</button>
        </div>
        {skuCheckLoading && <div className="rounded-lg border border-blue-200 bg-blue-50 p-3 text-sm text-blue-800">Проверка SKU в базе...</div>}
        {skuCheckError && (
          <div className="flex flex-wrap items-center gap-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            <span>{skuCheckError}</span>
            <button type="button" className="border border-red-200 bg-white text-red-700" onClick={() => void retrySkuPreflight()} disabled={busy || skuCheckLoading}>Повторить проверку SKU</button>
          </div>
        )}
        {hasRows && !skuCheckLoading && !skuCheckError && <div className="rounded-lg border border-green-200 bg-green-50 p-3 text-sm text-green-700">Проверка SKU в базе выполнена.</div>}
      </section>

      {error && <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-red-700">{error}</div>}
      {success && <div className="rounded-xl border border-green-200 bg-green-50 p-4 text-green-700">{success}</div>}

      {hasRows && (
        <section className="space-y-4 rounded-xl bg-white p-6 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-xl font-semibold">Review table</h2>
              <p className="text-sm text-slate-500">Выбрано {selectedRows.length}, готово к импорту {importableRows.length}. Missing images остаются предупреждением: фото нужны перед публикацией.</p>
              {hasExistingSkuConflicts && <p className="mt-2 text-sm font-medium text-red-700">Найдены SKU, которые уже есть в каталоге. Эти строки нельзя импортировать повторно.</p>}
            </div>
            <div className="flex max-w-xl flex-col items-start gap-3">
              <label className="flex items-start gap-3 rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
                <input
                  type="checkbox"
                  style={{ width: 'auto' }}
                  checked={importConfirmed}
                  disabled={busy || importBlockedBySkuCheck || importableRows.length === 0 || hasSelectedInvalidRows}
                  onChange={(event) => setImportConfirmed(event.target.checked)}
                />
                <span>
                  Я понимаю, что выбранные строки будут созданы в staging как черновики.
                  <span className="mt-1 block text-xs text-slate-500">Импорт остаётся draft-only; предупреждения по изображениям нужно закрыть перед публикацией.</span>
                </span>
              </label>
              <button type="button" className="bg-green-700 text-white disabled:opacity-50" disabled={busy || importBlockedBySkuCheck || importableRows.length === 0 || hasSelectedInvalidRows || !importConfirmed} onClick={importSelected}>
                {busy ? 'Импорт...' : 'Import selected as drafts'}
              </button>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full min-w-[1180px] text-left text-sm">
              <thead className="bg-slate-50 text-slate-600">
                <tr>
                  <th className="p-2"><input aria-label="Выбрать все строки" type="checkbox" style={{ width: 'auto' }} checked={rows.every((row) => row.selected)} onChange={(event) => toggleAll(event.target.checked)} /></th>
                  <th className="p-2">Status</th>
                  <th className="p-2">SKU</th>
                  <th className="p-2">Name</th>
                  <th className="p-2">Category</th>
                  <th className="p-2">Price</th>
                  <th className="p-2">Stock</th>
                  <th className="p-2">Images</th>
                  <th className="p-2">Warnings / errors</th>
                  <th className="p-2">Source URL</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id} className="border-t align-top">
                    <td className="p-2"><input aria-label={`Выбрать строку ${row.sourceIndex + 1}`} type="checkbox" style={{ width: 'auto' }} checked={row.selected} onChange={(event) => updateRow(row.id, 'selected', event.target.checked)} /></td>
                    <td className="p-2">
                      <span className={`rounded px-2 py-1 text-xs font-semibold ${row.errors.length > 0 ? 'bg-red-100 text-red-700' : row.warnings.length > 0 ? 'bg-yellow-100 text-yellow-800' : 'bg-green-100 text-green-700'}`}>
                        {row.errors.length > 0 ? 'error' : row.warnings.length > 0 ? 'warning' : 'valid'}
                      </span>
                      <div className="mt-2 text-xs text-slate-500">will import as draft</div>
                    </td>
                    <td className="p-2"><input value={row.sku} onChange={(event) => updateRow(row.id, 'sku', event.target.value)} /></td>
                    <td className="p-2"><input value={row.name} onChange={(event) => updateRow(row.id, 'name', event.target.value)} /></td>
                    <td className="p-2"><input value={row.category} onChange={(event) => updateRow(row.id, 'category', event.target.value)} /></td>
                    <td className="p-2"><input inputMode="decimal" value={row.price_per_meter} onChange={(event) => updateRow(row.id, 'price_per_meter', event.target.value)} /></td>
                    <td className="p-2">
                      <select value={row.stock_status} onChange={(event) => updateRow(row.id, 'stock_status', event.target.value as FabricImportRow['stock_status'])}>
                        <option value="">Нужно выбрать</option>
                        <option value="unknown">unknown</option>
                        {IMPORT_STOCK_STATUS_VALUES.map((value) => <option key={value} value={value}>{STOCK_LABELS[value]}</option>)}
                      </select>
                    </td>
                    <td className="p-2">{row.imageCount}</td>
                    <td className="p-2">
                      {row.errors.length > 0 && <ul className="list-disc pl-4 text-red-700">{row.errors.map((item) => <li key={item}>{item}</li>)}</ul>}
                      {row.warnings.length > 0 && <ul className="mt-2 list-disc pl-4 text-yellow-800">{row.warnings.map((item) => <li key={item}>{item}</li>)}</ul>}
                    </td>
                    <td className="max-w-[220px] truncate p-2 text-xs text-slate-500">{row.source_url || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {result && (
        <section className="rounded-xl bg-white p-6 shadow-sm">
          <h2 className="text-xl font-semibold">Результат импорта</h2>
          <p className="text-slate-600">Создано: {result.created}. Ошибок/пропусков: {result.skipped}.</p>
          <div className="mt-4 overflow-x-auto">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead className="bg-slate-50 text-slate-600"><tr><th className="p-2">SKU</th><th className="p-2">Status</th><th className="p-2">Message</th><th className="p-2">Created ID</th></tr></thead>
              <tbody>
                {result.rows.map((row) => (
                  <tr key={`${row.sku}-${row.message}`} className="border-t"><td className="p-2 font-mono text-xs">{row.sku}</td><td className="p-2">{row.status}</td><td className="p-2">{row.message}</td><td className="p-2 font-mono text-xs">{row.id ?? '—'}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
