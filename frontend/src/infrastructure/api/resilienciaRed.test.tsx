import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  AxiosError,
  type AxiosAdapter,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
} from 'axios';
import { QueryClientProvider, useQuery } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import apiClient from '@/infrastructure/config/apiClient';
import { evidenciaService } from '@/infrastructure/api/EvidenciaService';
import {
  esResultadoIncierto,
  getApiErrorMessage,
  isOfflineError,
} from '@/infrastructure/api/errors';
import { createQueryClient, shouldRetryQuery } from '@/infrastructure/api/queryClient';
import {
  fetchCollection,
  fetchItemById,
  mergeById,
  upsertById,
  type FetchStatus,
} from '@/infrastructure/stores/asyncCollection';
import {
  errorInternoGateway,
  gatewaySaturada,
  servicioInalcanzable,
  tiempoAgotado,
} from '@/infrastructure/mocks/payloads.reales';

/**
 * Pruebas de resiliencia sobre el transporte real (Axios), no sobre servicios
 * mockeados: el adaptador reemplaza la red, pero pasan por los interceptores,
 * la clasificación de errores, React Query y el helper de colecciones.
 *
 * Cubre los tres escenarios de la tarea:
 * - timeout del cliente (30 s generales / 120 s de evidencias);
 * - respuestas 5xx (500 frente a 502/503/504) y su reintento;
 * - pérdida temporal de conectividad y recuperación en el reintento.
 */

const originalAdapter = apiClient.defaults.adapter;

interface TestItem {
  id: string;
  name: string;
}

interface TestState {
  items: TestItem[];
  status: FetchStatus;
  error: string | null;
  isOffline: boolean;
  requestId: string | null;
}

let state: TestState;
const set = (patch: Partial<TestState> | ((s: TestState) => Partial<TestState>)) => {
  state = { ...state, ...(typeof patch === 'function' ? patch(state) : patch) };
};

const evidenciaApi = {
  evidencia_id: '3f2b8c1e-5d4a-4e6b-9c7d-1a2b3c4d5e6f',
  orden_id: 31,
  presupuesto_id: null,
  contexto: 'diagnostico' as const,
  tipo_archivo: 'foto' as const,
  visible_cliente: false,
  estado: 'confirmada' as const,
  nombre_original: 'frenos delanteros.jpg',
  content_type: 'image/jpeg',
  tamano_bytes: 482133,
  creada_en: '2026-10-07T10:15:00-03:00',
};

function respuesta<T>(config: InternalAxiosRequestConfig, status: number, data: T): AxiosResponse<T> {
  return { data, status, statusText: `Respuesta ${status}`, headers: {}, config };
}

function errorConRespuesta(
  config: InternalAxiosRequestConfig,
  status: number,
  data: unknown
): AxiosError {
  return new AxiosError(
    `Request failed with status code ${status}`,
    AxiosError.ERR_BAD_RESPONSE,
    config,
    undefined,
    respuesta(config, status, data)
  );
}

function errorDeTimeout(config: InternalAxiosRequestConfig): AxiosError {
  // Es la forma exacta en que Axios rechaza al vencer `config.timeout`:
  // no hay respuesta HTTP y el código es ECONNABORTED.
  return new AxiosError(
    `timeout of ${config.timeout ?? 0}ms exceeded`,
    AxiosError.ECONNABORTED,
    config
  );
}

function errorDeRed(config: InternalAxiosRequestConfig): AxiosError {
  return new AxiosError('Network Error', AxiosError.ERR_NETWORK, config);
}

function adaptadorQueFalla(crearError: (config: InternalAxiosRequestConfig) => AxiosError): AxiosAdapter {
  return async (config) => {
    throw crearError(config);
  };
}

function adaptadorQueResponde(status: number, data: unknown): AxiosAdapter {
  return async (config) => {
    if (status >= 200 && status < 300) return respuesta(config, status, data);
    throw errorConRespuesta(config, status, data);
  };
}

/** Ejecuta una promesa que debe rechazar y devuelve el error para inspeccionarlo. */
async function capturarError(promesa: Promise<unknown>): Promise<unknown> {
  try {
    await promesa;
    throw new Error('Se esperaba un rechazo y la promesa se resolvió');
  } catch (error) {
    return error;
  }
}

beforeEach(() => {
  localStorage.clear();
  state = { items: [], status: 'idle', error: null, isOffline: false, requestId: null };
});

afterEach(() => {
  apiClient.defaults.adapter = originalAdapter;
  vi.restoreAllMocks();
});

describe('timeouts de red', () => {
  it('el cliente general corta a los 30 s y la subida de evidencias a los 120 s', async () => {
    const configuraciones: Array<{ url?: string; timeout?: number }> = [];
    apiClient.defaults.adapter = async (config) => {
      configuraciones.push({ url: config.url, timeout: config.timeout });
      if (config.url === '/evidencias') return respuesta(config, 201, evidenciaApi);
      return respuesta(config, 200, []);
    };

    expect(apiClient.defaults.timeout).toBe(30000);

    await apiClient.get('/ordenes');
    await evidenciaService.crear({
      ordenId: '31',
      archivo: new File(['contenido'], 'frenos.jpg', { type: 'image/jpeg' }),
      contexto: 'diagnostico',
    });

    expect(configuraciones).toEqual([
      { url: '/ordenes', timeout: 30000 },
      { url: '/evidencias', timeout: 120000 },
    ]);
  });

  it('un timeout se presenta como caída de conexión y es reintentable', async () => {
    apiClient.defaults.adapter = adaptadorQueFalla(errorDeTimeout);

    const error = await capturarError(apiClient.get('/ordenes'));

    expect((error as AxiosError).code).toBe('ECONNABORTED');
    expect(isOfflineError(error)).toBe(true);
    expect(getApiErrorMessage(error)).toMatch(/No se pudo conectar con el servidor/);
    expect(shouldRetryQuery(0, error)).toBe(true);
    // Una escritura cortada por timeout pudo aplicarse igual: hay que comprobar
    // el estado antes de repetirla.
    expect(esResultadoIncierto(error)).toBe(true);
  });

  it('un timeout durante la subida de evidencia no se confunde con un rechazo del servidor', async () => {
    apiClient.defaults.adapter = adaptadorQueFalla(errorDeTimeout);

    const error = await capturarError(
      evidenciaService.crear({
        ordenId: '31',
        archivo: new File(['contenido'], 'video.mp4', { type: 'video/mp4' }),
        contexto: 'reparacion',
      })
    );

    expect(isOfflineError(error)).toBe(true);
    expect(getApiErrorMessage(error)).toMatch(/No se pudo conectar con el servidor/);
    expect(esResultadoIncierto(error)).toBe(true);
  });
});

describe('respuestas 5xx', () => {
  it.each([
    {
      status: 500,
      cuerpo: errorInternoGateway,
      offline: false,
      mensaje: 'Ocurrió un error inesperado en la Gateway.',
      incierto: true,
    },
    {
      status: 502,
      cuerpo: servicioInalcanzable,
      offline: true,
      mensaje: 'El servicio no está disponible. Intente más tarde.',
      incierto: true,
    },
    {
      status: 503,
      cuerpo: gatewaySaturada,
      offline: true,
      mensaje: 'La Gateway está ocupada. Intente más tarde.',
      incierto: true,
    },
    {
      status: 504,
      cuerpo: tiempoAgotado,
      offline: true,
      mensaje: 'El servicio tardó demasiado en responder. Intente más tarde.',
      incierto: true,
    },
  ])(
    'un $status conserva el mensaje real, se clasifica bien y es reintentable',
    async ({ status, cuerpo, offline, mensaje, incierto }) => {
      apiClient.defaults.adapter = adaptadorQueResponde(status, cuerpo);

      const error = await capturarError(apiClient.get('/ordenes'));

      expect(isOfflineError(error)).toBe(offline);
      expect(getApiErrorMessage(error)).toBe(mensaje);
      expect(shouldRetryQuery(0, error)).toBe(true);
      expect(esResultadoIncierto(error)).toBe(incierto);
    }
  );

  it('un 500 propio del microservicio no es incierto: el servicio rechazó la escritura', async () => {
    // A diferencia del 500 de la Gateway, este llega sin bloque `error`, así que
    // no hay código que sugiera que la operación pudo aplicarse.
    apiClient.defaults.adapter = adaptadorQueResponde(500, {
      detail: 'No fue posible consultar los vehículos',
    });

    const error = await capturarError(apiClient.get('/vehiculos'));

    expect(isOfflineError(error)).toBe(false);
    expect(getApiErrorMessage(error)).toBe('No fue posible consultar los vehículos');
    expect(esResultadoIncierto(error)).toBe(false);
  });
});

describe('pérdida temporal de conectividad', () => {
  it('la caché se conserva durante la caída y el reintento la actualiza al volver la red', async () => {
    let intento = 0;
    apiClient.defaults.adapter = async (config) => {
      intento += 1;
      if (intento === 1) throw errorDeRed(config);
      return respuesta(config, 200, [
        { id: '1', name: 'actualizado' },
        { id: '2', name: 'nuevo' },
      ]);
    };
    state = {
      items: [{ id: '1', name: 'en caché' }],
      status: 'success',
      error: null,
      isOffline: false,
      requestId: null,
    };
    const loader = () => apiClient.get<TestItem[]>('/vehiculos').then((res) => res.data);

    await fetchCollection<TestItem, TestState>(loader, set, (s, fetched) => ({
      items: mergeById(s.items, fetched),
    }));

    // Primer intento: sin red. La vista conserva lo último que mostró y marca
    // el modo offline con un mensaje accionable.
    expect(state.status).toBe('error');
    expect(state.isOffline).toBe(true);
    expect(state.error).toMatch(/No se pudo conectar con el servidor/);
    expect(state.items).toEqual([{ id: '1', name: 'en caché' }]);

    // Segundo intento (botón Reintentar): la red volvió y el estado se limpia.
    await fetchCollection<TestItem, TestState>(loader, set, (s, fetched) => ({
      items: mergeById(s.items, fetched),
    }));

    expect(state.status).toBe('success');
    expect(state.isOffline).toBe(false);
    expect(state.error).toBeNull();
    expect(state.requestId).toBeNull();
    expect(state.items).toEqual([
      { id: '1', name: 'actualizado' },
      { id: '2', name: 'nuevo' },
    ]);
  });

  it('el detalle conserva la copia local cuando la red cae y se actualiza al reintentar', async () => {
    let intento = 0;
    apiClient.defaults.adapter = async (config) => {
      intento += 1;
      if (intento === 1) throw errorDeTimeout(config);
      return respuesta(config, 200, { id: '7', name: 'servidor' });
    };
    state = {
      items: [{ id: '7', name: 'en caché' }],
      status: 'success',
      error: null,
      isOffline: false,
      requestId: null,
    };
    const loader = (id: string) =>
      apiClient.get<TestItem>(`/vehiculos/${id}`).then((res) => res.data);

    const primero = await fetchItemById<TestItem, TestState>(
      '7',
      loader,
      set,
      () => state.items,
      (s, item) => ({ items: upsertById(s.items, item) })
    );

    // Sin red pero con copia local: la vista puede seguir mostrando el detalle.
    expect(primero).toEqual({ item: { id: '7', name: 'en caché' }, notFound: false, failed: false });
    expect(state.isOffline).toBe(true);
    expect(state.error).toMatch(/No se pudo conectar con el servidor/);

    const segundo = await fetchItemById<TestItem, TestState>(
      '7',
      loader,
      set,
      () => state.items,
      (s, item) => ({ items: upsertById(s.items, item) })
    );

    expect(segundo.item).toEqual({ id: '7', name: 'servidor' });
    expect(state.isOffline).toBe(false);
    expect(state.error).toBeNull();
    expect(state.items).toEqual([{ id: '7', name: 'servidor' }]);
  });

  it('React Query reintenta un 503 transitorio y termina mostrando los datos', async () => {
    let intentos = 0;
    apiClient.defaults.adapter = async (config) => {
      intentos += 1;
      if (intentos <= 2) throw errorConRespuesta(config, 503, gatewaySaturada);
      return respuesta(config, 200, [{ id: '1' }]);
    };

    function Sonda() {
      const { data, status } = useQuery({
        queryKey: ['resiliencia-503'],
        queryFn: () => apiClient.get<Array<{ id: string }>>('/ordenes').then((res) => res.data),
        // Sin espera entre reintentos: la prueba mide el comportamiento, no el backoff.
        retryDelay: 0,
      });
      return (
        <div data-testid="sonda">
          {status}:{data?.[0]?.id ?? ''}
        </div>
      );
    }

    const client = createQueryClient();
    render(
      <QueryClientProvider client={client}>
        <Sonda />
      </QueryClientProvider>
    );

    await waitFor(
      () => expect(screen.getByTestId('sonda')).toHaveTextContent('success:1'),
      { timeout: 5000 }
    );
    // Fallo inicial + dos reintentos automáticos permitidos.
    expect(intentos).toBe(3);
    client.clear();
  });

  it('si el 503 persiste, React Query se detiene tras dos reintentos y deja el error', async () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    let intentos = 0;
    apiClient.defaults.adapter = async (config) => {
      intentos += 1;
      throw errorConRespuesta(config, 503, gatewaySaturada);
    };

    function Sonda() {
      const { status } = useQuery({
        queryKey: ['resiliencia-503-persistente'],
        queryFn: () => apiClient.get('/ordenes'),
        retryDelay: 0,
      });
      return <div data-testid="sonda">{status}</div>;
    }

    const client = createQueryClient();
    render(
      <QueryClientProvider client={client}>
        <Sonda />
      </QueryClientProvider>
    );

    await waitFor(
      () => expect(screen.getByTestId('sonda')).toHaveTextContent('error'),
      { timeout: 5000 }
    );
    expect(intentos).toBe(3);
    // El fallo queda registrado con el mensaje normalizado, sin volcar el token.
    expect(consoleSpy).toHaveBeenCalledWith(
      '[React Query] Fallo de consulta',
      'queryKey=["resiliencia-503-persistente"]',
      expect.stringContaining('mensaje=La Gateway está ocupada. Intente más tarde.'),
      expect.stringContaining('request-id=')
    );
    client.clear();
    consoleSpy.mockRestore();
  });
});
