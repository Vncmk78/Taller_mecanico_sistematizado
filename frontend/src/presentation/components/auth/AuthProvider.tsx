import { useEffect, useMemo, useRef, type ReactNode } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import type { AxiosError } from 'axios';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { getApiErrorMessage } from '@/infrastructure/api/errors';
import { setForbiddenHandler, setUnauthorizedHandler } from '@/infrastructure/config/apiClient';
import { AuthContext, type AuthContextValue } from '@/presentation/components/auth/authContext';
import { getUserRoles, hasAllRoles, hasAnyRole } from '@/presentation/utils/roleVisibility';

export function AuthProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const location = useLocation();
  // Ruta vigente del router (no window.location, que no refleja MemoryRouter).
  const rutaActual = useRef(location);
  useEffect(() => {
    rutaActual.current = location;
  }, [location]);
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
      // Si ya se está en /login (por ejemplo, un segundo 401 de la misma
      // restauración), no se navega otra vez: se perdería la ruta pedida.
      const { pathname, search } = rutaActual.current;
      if (pathname === '/login') return;
      navigate('/login', { replace: true, state: { from: pathname + search } });
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

  // Una sola restauración por montaje: en desarrollo, StrictMode repite los
  // efectos y la segunda consulta de /auth/me duplicaba el 401.
  const restauracionIniciada = useRef(false);
  useEffect(() => {
    if (restauracionIniciada.current) return;
    restauracionIniciada.current = true;
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