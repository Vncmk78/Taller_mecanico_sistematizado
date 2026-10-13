import { describe, expect, it } from 'vitest';
import { formatBytes } from './evidenceDisplay';

describe('formatBytes', () => {
    it('muestra bytes sin decimales', () => {
        expect(formatBytes(512)).toBe('512 B');
    });

    it('escala a KB y MB con separador decimal chileno', () => {
        expect(formatBytes(1024)).toBe('1 KB');
        expect(formatBytes(482133)).toBe('470,8 KB');
        expect(formatBytes(6 * 1024 * 1024)).toBe('6 MB');
    });

    it('tolera valores no válidos', () => {
        expect(formatBytes(0)).toBe('0 B');
        expect(formatBytes(-10)).toBe('0 B');
    });
});
