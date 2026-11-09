import { create } from 'zustand';
import type { User } from '@/domain/entities/User';
import { perfilClienteService } from '@/infrastructure/api/PerfilClienteService';
import { getApiErrorMessage, isConflictError, isOfflineError } from '@/infrastructure/api/errors';

/**
 * Preparación del perfil Cliente de MS2 tras iniciar sesión.
 *
 * MS1 crea la cuenta; MS2 necesita además su propio perfil Cliente para que
 * vehículos y órdenes funcionen. El backend garantiza la idempotencia, así que
 * la web puede pedir la preparación en cada inicio de sesión y reintentarla si
 * falla, sin registrar la cuenta otra vez.
 */
export type EstadoPerfilCliente = 'pendiente' | 'preparando' | 'listo' | 'error';

interface TelefonoPendiente {
  email: string;
  telefono: string;
}

interface PerfilClienteState {
  estado: EstadoPerfilCliente;
  /** Usuario (id de MS1) cuyo perfil quedó listo en esta sesión. */
  usuarioPreparado: string | null;
  error: string | null;
  /** Aviso no bloqueante (por ejemplo, teléfono no aplicado). */
  aviso: string | null;
  /**
   * Teléfono que el visitante escribió al registrarse. Solo vive en memoria
   * hasta el primer inicio de sesión de esa cuenta; si se pierde (recarga), el
   * perfil se prepara sin teléfono, que es opcional.
   */
  telefonoPendiente: TelefonoPendiente | null;
  recordarTelefono: (email: string, telefono: string | undefined) => void;
  preparar: (user: User) => Promise<void>;
  descartarAviso: () => void;
  reset: () => void;
}

const normalizarCorreo = (email: string) => email.trim().toLowerCase();

const ESTADO_INICIAL = {
  estado: 'pendiente' as EstadoPerfilCliente,
  usuarioPreparado: null,
  error: null,
  aviso: null,
  telefonoPendiente: null,
};

// Una sola preparación en vuelo por usuario: evita llamadas duplicadas por
// re-renderizados o por el doble efecto de React StrictMode.
let enCurso: { usuarioId: string; promesa: Promise<void> } | null = null;

export const usePerfilClienteStore = create<PerfilClienteState>((set, get) => ({
  ...ESTADO_INICIAL,

  recordarTelefono: (email, telefono) => {
    const limpio = telefono?.trim();
    set({
      telefonoPendiente: limpio ? { email: normalizarCorreo(email), telefono: limpio } : null,
    });
  },

  preparar: (user) => {
    const { estado, usuarioPreparado } = get();
    if (estado === 'listo' && usuarioPreparado === user.id) return Promise.resolve();
    if (enCurso && enCurso.usuarioId === user.id) return enCurso.promesa;

    const pendiente = get().telefonoPendiente;
    const telefono =
      pendiente && pendiente.email === normalizarCorreo(user.email) ? pendiente.telefono : undefined;

    set({ estado: 'preparando', error: null });
    const promesa = (async () => {
      try {
        await perfilClienteService.preparar(telefono);
        set({ estado: 'listo', usuarioPreparado: user.id, telefonoPendiente: null });
      } catch (error) {
        if (isConflictError(error)) {
          // El perfil existe (no se sobrescribe): se puede continuar.
          set({
            estado: 'listo',
            usuarioPreparado: user.id,
            telefonoPendiente: null,
            aviso:
              'Tu perfil de cliente ya existía con otro teléfono; se conservó el registrado.',
          });
          return;
        }
        set({
          estado: 'error',
          error: isOfflineError(error)
            ? 'No se pudo conectar con el servidor. Verifique su conexión e intente nuevamente.'
            : getApiErrorMessage(error, 'No fue posible preparar el perfil de cliente.'),
        });
      } finally {
        enCurso = null;
      }
    })();
    enCurso = { usuarioId: user.id, promesa };
    return promesa;
  },

  descartarAviso: () => set({ aviso: null }),

  reset: () => {
    enCurso = null;
    set({ ...ESTADO_INICIAL });
  },
}));
