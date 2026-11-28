import { describe, expect, it, vi } from 'vitest';
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

  it('envía FormData con boundary multipart usando fetch', async () => {
    const baseOriginal = apiClient.defaults.baseURL;
    apiClient.defaults.baseURL = 'https://ejemplo.test/api';

    let cabeceras: Headers | undefined;
    let metodo = '';

    vi.stubGlobal(
      'fetch',
      async (entrada: RequestInfo | URL, init?: RequestInit) => {
        const peticion = entrada instanceof Request ? entrada : new Request(entrada, init);
        cabeceras = peticion.headers;
        metodo = peticion.method;
        return new Response('{}', {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
    );

    const form = new FormData();
    form.append('archivo', new Blob(['x'], { type: 'image/png' }), 'x.png');

    try {
      await apiClient.post('/evidencias', form);
      expect(metodo).toBe('POST');
      expect(cabeceras?.get('content-type')).toMatch(/^multipart\/form-data; boundary=/);
    } finally {
      vi.unstubAllGlobals();
      apiClient.defaults.baseURL = baseOriginal;
    }
  });
});
