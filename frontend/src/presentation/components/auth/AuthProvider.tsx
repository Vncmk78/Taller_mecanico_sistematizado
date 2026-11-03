import { useEffect, useMemo, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import type { AxiosError } from 'axios';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { getApiErrorMessage } from '@/infrastructure/api/errors';
import { setForbiddenHandler, setUnauthorizedHandler } from '@/infrastructure/config/apiClient';
import { AuthContext, type AuthContextValue } from '@/presentation/components/auth/authContext';
import { getUserRoles, hasAllRoles, hasAnyRole } from '@/presentation/utils/roleVisibility';

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
      const message = getApiErrorMessage(error, 'No tiene permisos para acceder a este recurso.');
      navigate('/acceso-denegado', { replace: true, state: { message } });
    });
    return () => {
      setUnauthorizedHandler(null);
      setForbiddenHandler(null);
    };
  }, [clearSession, navigate]);

  useEffect(() => {
    void restoreSession();
  }, [restoreSession]);

  const roles = useMemo(() => getUserRoles(user), [user]);

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
      roles,
      hasRole: (...rolesToCheck) => hasAnyRole(user, ...rolesToCheck),
      hasAnyRole: (...rolesToCheck) => hasAnyRole(user, ...rolesToCheck),
      hasAllRoles: (...rolesToCheck) => hasAllRoles(user, ...rolesToCheck),
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
      roles,
    ]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}