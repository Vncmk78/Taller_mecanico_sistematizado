import { create } from 'zustand';
import type { User } from '@/domain/entities/User';
import { getToken, removeToken, setToken } from '../config/tokenStorage';
import { getTokenExpiryMs } from '../config/sessionExpiry';
import { authService } from '../api/AuthService';
import { useOrderStore } from './useOrderStore';
import { usePerfilClienteStore } from './usePerfilClienteStore';
import { useVehicleStore } from './useVehicleStore';

/**
 * Las cachés de órdenes y vehículos viven en memoria y son compartidas entre los
 * tres portales, así que sobreviven a un cambio de sesión en el mismo navegador.
 * Se vacían al cerrar sesión para que el siguiente usuario no herede los datos
 * del anterior.
 */
function purgeSharedCaches(): void {
  useOrderStore.getState().reset();
  useVehicleStore.getState().reset();
  usePerfilClienteStore.getState().reset();
}

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  isInitializing: boolean;
  /**
   * Motivo del último cierre de sesión. Vive en el store y no solo en el state
   * del router porque el `<Navigate>` de `ProtectedRoute` puede ganarle la
   * carrera a la redirección del handler y perdería el aviso.
   */
  sesionExpirada: boolean;
  login: (email: string, password: string) => Promise<User>;
  logout: () => void;
  setUser: (user: User) => void;
  getProfile: () => Promise<User>;
  restoreSession: () => Promise<void>;
  clearSession: () => void;
  marcarSesionExpirada: (expirada: boolean) => void;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  token: getToken(),
  isAuthenticated: getToken() !== null,
  isLoading: false,
  sesionExpirada: false,
  // Con un token guardado la sesión aún no está verificada (el usuario se
  // obtiene con GET /auth/me). Se parte "inicializando" para que las rutas
  // protegidas esperen esa restauración en lugar de redirigir al login: así
  // una recarga o un enlace directo (/admin/ordenes/12) conserva la ruta.
  isInitializing: getToken() !== null,

  login: async (email: string, password: string) => {
    set({ isLoading: true });
    try {
      const auth = await authService.login({ email, password });
      setToken(auth.access_token);
      set({
        user: auth.user,
        token: auth.access_token,
        isAuthenticated: true,
        isLoading: false,
        sesionExpirada: false,
      });
      return auth.user;
    } catch (error) {
      set({ isLoading: false });
      throw error;
    }
  },

  logout: () => {
    removeToken();
    purgeSharedCaches();
    set({ user: null, token: null, isAuthenticated: false, sesionExpirada: false });
  },

  setUser: (user: User) => set({ user }),

  marcarSesionExpirada: (expirada: boolean) => set({ sesionExpirada: expirada }),

  getProfile: async () => {
    const user = await authService.getProfile();
    set({ user });
    return user;
  },

  restoreSession: async () => {
    if (!get().token) {
      set({ isAuthenticated: false, isInitializing: false });
      return;
    }
    // Si el JWT guardado ya venció, no tiene sentido gastar una petición en
    // /auth/me: se descarta igual que un 401, pero sin anunciar "sesión
    // expirada" (la app se abrió con una sesión que ya no existía).
    const expiraEn = getTokenExpiryMs(get().token);
    if (expiraEn !== null && expiraEn <= Date.now()) {
      get().clearSession();
      set({ isInitializing: false });
      return;
    }
    if (get().user) {
      set({ isAuthenticated: true, isInitializing: false });
      return;
    }
    set({ isInitializing: true });
    try {
      const user = await authService.getProfile();
      set({ user, isAuthenticated: true, isInitializing: false });
    } catch {
      removeToken();
      set({
        user: null,
        token: null,
        isAuthenticated: false,
        isInitializing: false,
      });
    }
  },

  clearSession: () => {
    removeToken();
    purgeSharedCaches();
    set({ user: null, token: null, isAuthenticated: false });
  },
}));