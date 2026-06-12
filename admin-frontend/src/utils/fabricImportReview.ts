import { FabricPayload, StockStatus } from '../api/fabrics';

export const IMPORT_STOCK_STATUS_VALUES = ['in_stock', 'preorder', 'out_of_stock'] as const;
export type ImportStockStatus = (typeof IMPORT_STOCK_STATUS_VALUES)[number];

export type FabricImportRow = {
  id: string;
  selected: boolean;
  sourceIndex: number;
  sku: string;
  name: string;
  category: string;
  price_per_meter: string;
  currency: string;
  stock_status: ImportStockStatus | 'unknown' | '';
  description_for_gpt: string;
  short_description: string;
  full_description: string;
  source_url: string;
  imageCount: number;
  imageEntries: unknown[];
  sourceWarnings: string[];
  errors: string[];
  warnings: string[];
};

type UnknownRecord = Record<string, unknown>;

function isRecord(value: unknown): value is UnknownRecord {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function text(value: unknown): string {
  return typeof value === 'string' ? value.trim() : value == null ? '' : String(value).trim();
}

function firstText(record: UnknownRecord, keys: string[]): string {
  for (const key of keys) {
    const value = text(record[key]);
    if (value) return value;
  }
  return '';
}

function nestedRecord(item: UnknownRecord, key: string): UnknownRecord | null {
  return isRecord(item[key]) ? item[key] : null;
}

function sourceRecord(item: UnknownRecord): UnknownRecord {
  return nestedRecord(item, 'normalized') ?? nestedRecord(item, 'raw') ?? item;
}

function parsePrice(value: unknown): string {
  if (typeof value === 'number' && Number.isFinite(value)) return String(value);
  const raw = text(value);
  if (!raw) return '';
  const match = raw.replace(/\u00a0/g, ' ').match(/(\d[\d\s]*(?:[,.]\d{1,2})?)/);
  if (!match) return '';
  const parsed = Number(match[1].replace(/\s+/g, '').replace(',', '.'));
  return Number.isFinite(parsed) && parsed >= 0 ? String(parsed) : '';
}

function imageEntriesFrom(item: UnknownRecord, source: UnknownRecord): unknown[] {
  const direct = item.images;
  if (Array.isArray(direct)) return direct;
  const raw = nestedRecord(item, 'raw');
  const sourceImages = source.image_urls ?? source.images ?? source.image ?? raw?.image_urls ?? raw?.images ?? raw?.image;
  if (Array.isArray(sourceImages)) return sourceImages;
  if (typeof sourceImages === 'string' && sourceImages.trim()) return [sourceImages.trim()];
  return [];
}

function sourceWarningsFrom(item: UnknownRecord): string[] {
  return Array.isArray(item.warnings) ? item.warnings.map(text).filter(Boolean) : [];
}

function normalizeStockStatus(value: unknown): FabricImportRow['stock_status'] {
  const raw = text(value);
  if (IMPORT_STOCK_STATUS_VALUES.includes(raw as ImportStockStatus)) return raw as ImportStockStatus;
  if (raw === 'unknown') return 'unknown';
  return '';
}

function duplicateSkus(rows: FabricImportRow[]): Set<string> {
  const counts = new Map<string, number>();
  rows.forEach((row) => {
    const key = row.sku.trim().toLowerCase();
    if (key) counts.set(key, (counts.get(key) ?? 0) + 1);
  });
  return new Set(Array.from(counts.entries()).filter(([, count]) => count > 1).map(([sku]) => sku));
}

export function validateFabricImportRows(rows: FabricImportRow[]): FabricImportRow[] {
  const duplicates = duplicateSkus(rows);
  return rows.map((row) => {
    const errors: string[] = [];
    const warnings = [...row.sourceWarnings];
    if (!row.sku.trim()) errors.push('SKU is required.');
    if (!row.name.trim()) errors.push('Name is required.');
    if (!row.category.trim()) errors.push('Category is required.');
    if (!IMPORT_STOCK_STATUS_VALUES.includes(row.stock_status as ImportStockStatus)) {
      errors.push('stock_status must be in_stock, preorder, or out_of_stock.');
    }
    if (duplicates.has(row.sku.trim().toLowerCase())) errors.push('Duplicate SKU in this import file.');
    if (!row.price_per_meter.trim()) warnings.push('Missing price_per_meter.');
    if (!row.description_for_gpt.trim()) warnings.push('Missing description_for_gpt.');
    if (row.imageCount === 0) warnings.push('Missing images; main and texture are required before publication.');
    return { ...row, errors: Array.from(new Set(errors)), warnings: Array.from(new Set(warnings)) };
  });
}

function rowFromItem(item: UnknownRecord, index: number): FabricImportRow {
  const source = sourceRecord(item);
  const images = imageEntriesFrom(item, source);
  const description = firstText(source, ['description_for_gpt', 'description_text', 'description', 'full_description']);
  const sourceWarnings = sourceWarningsFrom(item);
  if (text(source.status) && text(source.status) !== 'draft') {
    sourceWarnings.push('Source status ignored; import target is draft.');
  }
  return {
    id: `row-${index + 1}`,
    selected: true,
    sourceIndex: index,
    sku: firstText(source, ['sku', 'article']),
    name: firstText(source, ['name', 'title']),
    category: firstText(source, ['category']),
    price_per_meter: parsePrice(source.price_per_meter ?? source.price ?? source.price_text),
    currency: firstText(source, ['currency']) || 'RUB',
    stock_status: normalizeStockStatus(source.stock_status),
    description_for_gpt: description,
    short_description: firstText(source, ['short_description', 'description_short']) || description,
    full_description: firstText(source, ['full_description', 'description_text', 'description']),
    source_url: firstText(item, ['source_url']) || firstText(source, ['source_url', 'url']) || firstText(nestedRecord(item, 'raw') ?? {}, ['source_url', 'url']),
    imageCount: images.length,
    imageEntries: images,
    sourceWarnings,
    errors: [],
    warnings: [],
  };
}

export function parseFabricImportJson(input: string): FabricImportRow[] {
  const parsed: unknown = JSON.parse(input);
  const rawItems = isRecord(parsed) && Array.isArray(parsed.items) ? parsed.items : Array.isArray(parsed) ? parsed : null;
  if (!rawItems) throw new Error('Import JSON must be an array or an object with an items array.');
  const rows = rawItems.filter(isRecord).map(rowFromItem);
  if (rows.length === 0) throw new Error('Import JSON does not contain fabric rows.');
  return validateFabricImportRows(rows);
}

function numberOrNull(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const parsed = Number(trimmed.replace(',', '.'));
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : null;
}

export function buildDraftFabricPayload(row: FabricImportRow): FabricPayload {
  return {
    sku: row.sku.trim(),
    name: row.name.trim(),
    category: row.category.trim(),
    price_per_meter: numberOrNull(row.price_per_meter),
    currency: row.currency.trim() || 'RUB',
    stock_status: row.stock_status as StockStatus,
    short_description: row.short_description.trim() || null,
    full_description: row.full_description.trim() || null,
    description_for_gpt: row.description_for_gpt.trim() || null,
    status: 'draft',
  };
}

export function buildCorrectedApprovedJson(rows: FabricImportRow[]): string {
  return `${JSON.stringify({
    items: rows.map((row) => ({
      normalized: buildDraftFabricPayload(row),
      images: row.imageEntries,
      source_url: row.source_url || undefined,
      warnings: row.warnings,
    })),
  }, null, 2)}\n`;
}
