import { describe, expect, it } from 'vitest';
import { buildCorrectedApprovedJson, buildDraftFabricPayload, EXISTING_SKU_ERROR, normalizeSkuKey, parseFabricImportJson, validateFabricImportRows } from './fabricImportReview';

describe('fabric import review helpers', () => {
  it('parses preview JSON with normalized rows and image warnings', () => {
    const rows = parseFabricImportJson(JSON.stringify({
      items: [
        {
          normalized: {
            sku: ' FAB-1 ',
            name: 'Silk',
            category: 'silk',
            price_per_meter: 1200,
            stock_status: 'preorder',
            description_for_gpt: 'Smooth silk.',
            status: 'published',
          },
          images: [],
          source_url: 'https://example.test/fab-1',
        },
      ],
    }));

    expect(rows).toHaveLength(1);
    expect(rows[0].sku).toBe('FAB-1');
    expect(rows[0].errors).toEqual([]);
    expect(rows[0].warnings).toContain('Missing images; main and texture are required before publication.');
    expect(buildDraftFabricPayload(rows[0])).toMatchObject({
      sku: 'FAB-1',
      status: 'draft',
      stock_status: 'preorder',
      price_per_meter: 1200,
    });
  });

  it('supports raw or flat items and rejects unknown stock status before import', () => {
    const rows = parseFabricImportJson(JSON.stringify([
      {
        raw: {
          article: 'RAW-1',
          title: 'Raw satin',
          category: 'satin',
          price_text: '2 100 RUB',
          stock_status: 'unknown',
          description_text: 'Raw source description.',
        },
      },
      {
        sku: 'FLAT-1',
        name: 'Flat satin',
        category: 'satin',
        stock_status: 'in_stock',
      },
    ]));

    expect(rows[0].sku).toBe('RAW-1');
    expect(rows[0].price_per_meter).toBe('2100');
    expect(rows[0].errors).toContain('stock_status must be in_stock, preorder, or out_of_stock.');
    expect(rows[1].errors).toEqual([]);
  });

  it('marks duplicate SKUs as errors before import', () => {
    const rows = parseFabricImportJson(JSON.stringify({
      items: [
        { normalized: { sku: 'DUP-1', name: 'One', category: 'silk', stock_status: 'preorder' } },
        { normalized: { sku: ' dup-1 ', name: 'Two', category: 'silk', stock_status: 'preorder' } },
      ],
    }));

    expect(rows[0].errors).toContain('Duplicate SKU in this import file.');
    expect(rows[1].errors).toContain('Duplicate SKU in this import file.');
  });

  it('marks existing backend SKUs as blocking errors before import', () => {
    const rows = parseFabricImportJson(JSON.stringify({
      items: [
        { normalized: { sku: 'EXISTING-1', name: 'Existing', category: 'silk', stock_status: 'preorder' } },
        { normalized: { sku: 'NEW-1', name: 'New', category: 'silk', stock_status: 'preorder' } },
      ],
    }), { existingSkuKeys: new Set(['existing-1']) });

    expect(rows[0].errors).toContain(EXISTING_SKU_ERROR);
    expect(rows[1].errors).not.toContain(EXISTING_SKU_ERROR);
  });

  it('normalizes existing SKU checks with trim and case-insensitive comparison', () => {
    const [row] = parseFabricImportJson(JSON.stringify({
      items: [{ normalized: { sku: ' Existing-Case ', name: 'Existing', category: 'silk', stock_status: 'preorder' } }],
    }), { existingSkuKeys: new Set([normalizeSkuKey('existing-case')]) });

    expect(row.errors).toContain(EXISTING_SKU_ERROR);
  });

  it('revalidates edited rows and exports corrected draft JSON only', () => {
    const [row] = parseFabricImportJson(JSON.stringify({
      items: [{ normalized: { sku: 'EDIT-1', name: 'Needs stock', category: 'silk', stock_status: 'unknown' } }],
    }));
    const [corrected] = validateFabricImportRows([{ ...row, stock_status: 'out_of_stock', price_per_meter: '99.50' }]);
    const json = JSON.parse(buildCorrectedApprovedJson([corrected]));

    expect(corrected.errors).toEqual([]);
    expect(json.items[0].normalized).toMatchObject({
      sku: 'EDIT-1',
      status: 'draft',
      stock_status: 'out_of_stock',
      price_per_meter: 99.5,
    });
    expect(JSON.stringify(json)).not.toContain('published');
  });
});
