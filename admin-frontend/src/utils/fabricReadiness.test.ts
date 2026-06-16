import { describe, expect, it } from 'vitest';
import { summarizeFabricReadiness } from './fabricReadiness';

describe('summarizeFabricReadiness', () => {
  it('labels ready fabrics', () => {
    const summary = summarizeFabricReadiness({
      public_catalog_ready: true,
      try_on_ready: true,
      missing_required_image_types: [],
      missing_upload_files: [],
      warnings: [],
    });

    expect(summary.label).toBe('Готово к публикации');
    expect(summary.tone).toBe('ready');
  });

  it('labels missing required image records', () => {
    const summary = summarizeFabricReadiness({
      public_catalog_ready: false,
      try_on_ready: false,
      missing_required_image_types: ['texture'],
      missing_upload_files: [],
      warnings: [],
    });

    expect(summary.label).toBe('Не готово: отсутствует texture');
    expect(summary.tone).toBe('warning');
  });

  it('labels missing backing upload files', () => {
    const summary = summarizeFabricReadiness({
      public_catalog_ready: false,
      try_on_ready: false,
      missing_required_image_types: [],
      missing_upload_files: [{ image_type: 'main', image_url: '/uploads/fabrics/missing.png', error_code: 'missing_file' }],
      warnings: [],
    });

    expect(summary.label).toBe('Файл изображения не найден: main');
    expect(summary.detail).toContain('Загрузите изображение заново');
  });
});
