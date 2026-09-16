import { create } from 'zustand';
import type { User } from '@/domain/entities/User';
import { authService } from '../api/AuthService';

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
  token: localStorage.getItem('token'),
  isAuthenticated: !!localStorage.getItem('token'),
  isLoading: false,
  isInitializing: false,

  login: async (email: string, password: string) => {
    set({ isLoading: true });
    try {
      const auth = await authService.login({ email, password });
      localStorage.setItem('token', auth.access_token);
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
    localStorage.removeItem('token');
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
      localStorage.removeItem('token');
      set({
        user: null,
        token: null,
        isAuthenticated: false,
        isInitializing: false,
      });
    }
  },

  clearSession: () => {
    localStorage.removeItem('token');
    set({ user: null, token: null, isAuthenticated: false });
  },
}));