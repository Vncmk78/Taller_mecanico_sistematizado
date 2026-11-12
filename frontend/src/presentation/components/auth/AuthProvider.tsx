import { useCallback, useEffect, useMemo, useRef, type ReactNode } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import type { AxiosError } from 'axios';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { getApiErrorMessage } from '@/infrastructure/api/errors';
import { setForbiddenHandler, setUnauthorizedHandler } from '@/infrastructure/config/apiClient';
import { AuthContext, type AuthContextValue } from '@/presentation/components/auth/authContext';
import { SessionExpiryBanner } from '@/presentation/components/auth/SessionExpiryBanner';
import { useSessionExpiry } from '@/presentation/components/auth/useSessionExpiry';
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
  const marcarSesionExpirada = useAuthStore((s) => s.marcarSesionExpirada);

  // Cierra la sesión una sola vez por token, ya sea porque la API respondió 401
  // o porque el `exp` del JWT venció mientras la app estaba en uso.
  const sesionCerrada = useRef(false);

  const cerrarPorExpiracion = useCallback(
    (anunciarExpiracion: boolean) => {
      if (sesionCerrada.current) return;
      sesionCerrada.current = true;
      // Solo se anuncia "sesión expirada" si había una sesión activa: abrir la
      // app con un token ya vencido no debe presentarse como una expiración en
      // curso.
      const habiaSesion = useAuthStore.getState().isAuthenticated;
      const anunciar = anunciarExpiracion && habiaSesion;
      // El aviso vive también en el store: el <Navigate> de ProtectedRoute
      // puede ganarle la carrera a esta redirección y perder el state.
      marcarSesionExpirada(anunciar);
      // Se navega antes de limpiar: si primero se limpia la sesión, el guard de
      // `ProtectedRoute` monta su propio <Navigate> y pisa el estado con el que
      // se anuncia la expiración (además pierde el query string).
      const { pathname, search } = rutaActual.current;
      if (pathname !== '/login') {
        navigate('/login', {
          replace: true,
          state: { from: pathname + search, sesionExpirada: anunciar },
        });
      }
      clearSession();
    },
    [clearSession, marcarSesionExpirada, navigate]
  );

  // Al iniciar sesión de nuevo, el guard vuelve a habilitarse.
  useEffect(() => {
    if (token) sesionCerrada.current = false;
  }, [token]);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      cerrarPorExpiracion(true);
    });
    setForbiddenHandler((error: AxiosError) => {
      const message = getApiErrorMessage(error, 'No tiene permisos para acceder a este recurso.');
      navigate('/acceso-denegado', { replace: true, state: { message } });
    });
    return () => {
      setUnauthorizedHandler(null);
      setForbiddenHandler(null);
    };
  }, [cerrarPorExpiracion, navigate]);

  // Una sola restauración por montaje: en desarrollo, StrictMode repite los
  // efectos y la segunda consulta de /auth/me duplicaba el 401.
  const restauracionIniciada = useRef(false);
  useEffect(() => {
    if (restauracionIniciada.current) return;
    restauracionIniciada.current = true;
    void restoreSession();
  }, [restoreSession]);

  const roles = useMemo(() => getUserRoles(user), [user]);

  // Cierre proactivo por `exp`: no depende de que la próxima petición reciba
  // un 401, así una pantalla sin tráfico no sigue mostrando una sesión muerta.
  const { minutosRestantes } = useSessionExpiry({ token, onExpired: cerrarPorExpiracion });

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

  return (
    <AuthContext.Provider value={value}>
      {children}
      <SessionExpiryBanner minutosRestantes={minutosRestantes} />
    </AuthContext.Provider>
  );
}