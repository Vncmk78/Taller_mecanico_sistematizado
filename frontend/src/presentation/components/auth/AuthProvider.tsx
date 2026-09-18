import { useEffect, useMemo, type ReactNode } from 'react';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { AuthContext, type AuthContextValue } from '@/presentation/components/auth/authContext';

export function AuthProvider({ children }: { children: ReactNode }) {
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