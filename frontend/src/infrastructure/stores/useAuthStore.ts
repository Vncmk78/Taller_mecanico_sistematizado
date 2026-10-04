import { create } from 'zustand';
import type { User } from '@/domain/entities/User';
import { getToken, removeToken, setToken } from '../config/tokenStorage';
import { authService } from '../api/AuthService';
import { useOrderStore } from './useOrderStore';
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
}

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  isInitializing: boolean;
  login: (email: string, password: string) => Promise<User>;
  logout: () => void;
  setUser: (user: User) => void;
  getProfile: () => Promise<User>;
  restoreSession: () => Promise<void>;
  clearSession: () => void;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  token: getToken(),
  isAuthenticated: getToken() !== null,
  isLoading: false,
  isInitializing: false,

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
    set({ user: null, token: null, isAuthenticated: false });
  },

  setUser: (user: User) => set({ user }),

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