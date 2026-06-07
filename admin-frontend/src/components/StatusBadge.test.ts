import { describe, expect, it } from 'vitest';
import { UNKNOWN_STATUS_LABEL, statusLabel } from './StatusBadge';

describe('StatusBadge generation statuses', () => {
  it.each([
    ['pending', 'В очереди'],
    ['processing', 'В работе'],
    ['completed', 'Готово'],
    ['failed', 'Ошибка'],
  ])('maps %s to a stable user-facing label', (status, label) => {
    expect(statusLabel(status)).toBe(label);
  });

  it('hides unknown raw status values', () => {
    const rawStatus = 'traceback Authorization: Bearer admin-token X-Bot-Token=secret-token';

    expect(statusLabel(rawStatus)).toBe(UNKNOWN_STATUS_LABEL);
    expect(statusLabel(rawStatus)).not.toContain('admin-token');
    expect(statusLabel(rawStatus)).not.toContain('X-Bot-Token');
    expect(statusLabel(rawStatus)).not.toContain('traceback');
  });
});
