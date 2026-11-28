import { describe, expect, it } from 'vitest';
import apiClient from './apiClient';

describe('apiClient: Content-Type', () => {
  it('conserva application/json para cuerpos JSON', async () => {
    const adaptadorOriginal = apiClient.defaults.adapter;
    let cabeceras: Record<string, unknown> | undefined;

    apiClient.defaults.adapter = async (config) => {
      cabeceras = config.headers.toJSON();
      return { data: {}, status: 200, statusText: 'OK', headers: {}, config };
    };

    try {
      await apiClient.post('/ejemplo', { dato: 1 });
      expect(cabeceras?.['Content-Type']).toBe('application/json');
    } finally {
      apiClient.defaults.adapter = adaptadorOriginal;
    }
  });

  it('retira el Content-Type global para FormData (axios genera el boundary)', async () => {
    const adaptadorOriginal = apiClient.defaults.adapter;
    let cabeceras: Record<string, unknown> | undefined;
    let cuerpo: unknown;

    apiClient.defaults.adapter = async (config) => {
      cabeceras = config.headers.toJSON();
      cuerpo = config.data;
      return { data: {}, status: 200, statusText: 'OK', headers: {}, config };
    };

    const form = new FormData();
    form.append('archivo', new Blob(['x'], { type: 'image/png' }), 'x.png');

    try {
      await apiClient.post('/evidencias', form);
      expect(cuerpo).toBe(form);
      expect(cabeceras?.['Content-Type']).not.toBe('application/json');
    } finally {
      apiClient.defaults.adapter = adaptadorOriginal;
    }
  });
});
