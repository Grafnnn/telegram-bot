import { describe, expect, it } from 'vitest';
import {
  ensureStockStatus,
  optionalNonNegativeNumber,
  optionalTrimmed,
  requiredNonNegativeNumber,
  requiredTrimmed,
  splitCsv,
} from './formValidation';

describe('admin form validation helpers', () => {
  it('trims required text and rejects blank values before submit', () => {
    expect(requiredTrimmed('  silk  ', 'Название')).toBe('silk');
    expect(() => requiredTrimmed('   ', 'Название')).toThrow('Название: заполните поле.');
  });

  it('normalizes optional text and comma-separated lists', () => {
    expect(optionalTrimmed('  описание  ')).toBe('описание');
    expect(optionalTrimmed('   ')).toBeNull();
    expect(splitCsv(' cotton,  silk ,, linen ')).toEqual(['cotton', 'silk', 'linen']);
    expect(splitCsv(' , ')).toBeNull();
  });

  it('rejects invalid or negative numeric values before submit', () => {
    expect(requiredNonNegativeNumber('12,50', 'Цена за метр')).toBe(12.5);
    expect(optionalNonNegativeNumber('', 'Количество на складе')).toBeNull();
    expect(() => requiredNonNegativeNumber('', 'Цена за метр')).toThrow('Цена за метр: заполните числовое поле.');
    expect(() => requiredNonNegativeNumber('-1', 'Цена за метр')).toThrow('Цена за метр: значение не может быть отрицательным.');
    expect(() => optionalNonNegativeNumber('nope', 'Количество на складе')).toThrow('Количество на складе: введите корректное число.');
  });

  it('rejects invalid stock statuses', () => {
    expect(ensureStockStatus('in_stock')).toBe('in_stock');
    expect(() => ensureStockStatus('reserved')).toThrow('Наличие: выберите корректный статус.');
  });
});
