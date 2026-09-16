import { create } from 'zustand';
import type { User } from '@/domain/entities/User';
import { authService } from '../api/AuthService';

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<User>;
  logout: () => void;
  setUser: (user: User) => void;
  getProfile: () => Promise<User>;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: localStorage.getItem('token'),
  isAuthenticated: !!localStorage.getItem('token'),
  isLoading: false,

  login: async (email: string, password: string) => {
    set({ isLoading: true });
    try {
      const { access_token, user } = await authService.login({ email, password });
      localStorage.setItem('token', access_token);
      set({ user, token: access_token, isAuthenticated: true, isLoading: false });
      return user;
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
}));