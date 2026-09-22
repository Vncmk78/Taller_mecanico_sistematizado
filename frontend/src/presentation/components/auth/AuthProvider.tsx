import { useEffect, useMemo, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import type { AxiosError } from 'axios';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { setForbiddenHandler, setUnauthorizedHandler } from '@/infrastructure/config/apiClient';
import { AuthContext, type AuthContextValue } from '@/presentation/components/auth/authContext';

export function AuthProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const token = useAuthStore((s) => s.token);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const isLoading = useAuthStore((s) => s.isLoading);
  const isInitializing = useAuthStore((s) => s.isInitializing);
  const login = useAuthStore((s) => s.login);
  const logout = useAuthStore((s) => s.logout);
  const restoreSession = useAuthStore((s) => s.restoreSession);
  const clearSession = useAuthStore((s) => s.clearSession);
  const getProfile = useAuthStore((s) => s.getProfile);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      clearSession();
      navigate('/login', { replace: true, state: { from: window.location.pathname } });
    });
    setForbiddenHandler((error: AxiosError) => {
      const detail = (error.response?.data as { detail?: string } | undefined)?.detail;
      navigate('/acceso-denegado', { replace: true, state: { message: detail } });
    });
    return () => {
      setUnauthorizedHandler(null);
      setForbiddenHandler(null);
    };
  }, [clearSession, navigate]);

  useEffect(() => {
    void restoreSession();
  }, [restoreSession]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      token,
      isAuthenticated,
      isLoading,
      isInitializing,
      login,
      logout,
      restoreSession,
      clearSession,
      getProfile,
      hasRole: (...roles) => (user ? roles.includes(user.role) : false),
    }),
    [
      user,
      token,
      isAuthenticated,
      isLoading,
      isInitializing,
      login,
      logout,
      restoreSession,
      clearSession,
      getProfile,
    ]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}