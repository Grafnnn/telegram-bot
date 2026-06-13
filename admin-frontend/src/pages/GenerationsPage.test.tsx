import { describe, expect, it } from 'vitest';
import type { Generation } from '../api/client';
import { generationFabricLabel, generationModeLabel, generationUserLabel } from './GenerationsPage';

describe('generation admin review helpers', () => {
  it('labels user-photo generations and linked fabric/user metadata', () => {
    const generation: Generation = {
      id: 'generation-id',
      mode: 'user_photo',
      status: 'completed',
      created_at: '2026-06-14T10:00:00Z',
      fabric: {
        id: 'fabric-id',
        sku: 'HQ-FABRIC-R2-001',
        name: 'Премиальный шелк',
        category: 'silk',
      },
      telegram_user: {
        id: 'user-id',
        telegram_id: 123456,
        username: 'staging_user',
      },
    };

    expect(generationModeLabel(generation.mode)).toBe('Примерка по фото');
    expect(generationFabricLabel(generation)).toBe('Премиальный шелк (HQ-FABRIC-R2-001)');
    expect(generationUserLabel(generation)).toBe('@staging_user');
  });

  it('keeps stable fallbacks for partial historical generation records', () => {
    const generation: Generation = {
      id: 'generation-id',
      fabric_id: 'fabric-id',
      telegram_user_id: 'telegram-user-id',
      mode: 'legacy-mode',
      status: 'failed',
      created_at: '2026-06-14T10:00:00Z',
    };

    expect(generationModeLabel(generation.mode)).toBe('legacy-mode');
    expect(generationFabricLabel(generation)).toBe('Ткань fabric-id');
    expect(generationUserLabel(generation)).toBe('Пользователь telegram-user-id');
  });
});
