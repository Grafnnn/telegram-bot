export const STOCK_STATUS_VALUES = ['in_stock', 'preorder', 'out_of_stock'] as const;

export type StockStatusValue = (typeof STOCK_STATUS_VALUES)[number];

export function requiredTrimmed(value: string, label: string): string {
  const trimmed = value.trim();
  if (!trimmed) throw new Error(`${label}: заполните поле.`);
  return trimmed;
}

export function optionalTrimmed(value: string): string | null {
  const trimmed = value.trim();
  return trimmed || null;
}

function parseNumber(value: string, label: string, required: boolean): number | null {
  const normalized = value.trim().replace(',', '.');
  if (!normalized) {
    if (required) throw new Error(`${label}: заполните числовое поле.`);
    return null;
  }
  const parsed = Number(normalized);
  if (!Number.isFinite(parsed)) throw new Error(`${label}: введите корректное число.`);
  if (parsed < 0) throw new Error(`${label}: значение не может быть отрицательным.`);
  return parsed;
}

export function requiredNonNegativeNumber(value: string, label: string): number {
  return parseNumber(value, label, true) as number;
}

export function optionalNonNegativeNumber(value: string, label: string): number | null {
  return parseNumber(value, label, false);
}

export function splitCsv(value: string): string[] | null {
  const items = value.split(',').map((item) => item.trim()).filter(Boolean);
  return items.length > 0 ? items : null;
}

export function ensureStockStatus(value: string): StockStatusValue {
  if (!STOCK_STATUS_VALUES.includes(value as StockStatusValue)) {
    throw new Error('Наличие: выберите корректный статус.');
  }
  return value as StockStatusValue;
}
