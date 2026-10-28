import { useMemo } from 'react';
import type { UserRole } from '@/domain/entities/User';
import { useAuth } from '@/presentation/components/auth/authContext';
import { canAccessRoute, canShow, getUserRoles, hasAllRoles, hasAnyRole } from '@/presentation/utils/roleVisibility';

export function useRoleAccess() {
    const auth = useAuth();
    const user = auth.user;
    const roles = useMemo(() => getUserRoles(user), [user]);

    return {
        user,
        roles,
        isAuthenticated: auth.isAuthenticated,
        isLoading: auth.isLoading,
        isInitializing: auth.isInitializing,
        token: auth.token,
        login: auth.login,
        logout: auth.logout,
        restoreSession: auth.restoreSession,
        clearSession: auth.clearSession,
        getProfile: auth.getProfile,
        hasRole: (...rolesToCheck: UserRole[]) => hasAnyRole(user, ...rolesToCheck),
        hasAnyRole: (...rolesToCheck: UserRole[]) => hasAnyRole(user, ...rolesToCheck),
        hasAllRoles: (...rolesToCheck: UserRole[]) => hasAllRoles(user, ...rolesToCheck),
        canShow: (rolesPermitidos: UserRole[]) => canShow(user, rolesPermitidos),
        canAccessRoute: (allowedRoles?: UserRole[]) => canAccessRoute(user, allowedRoles),
    };
}
