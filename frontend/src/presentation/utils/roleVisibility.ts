import type { User, UserRole } from '@/domain/entities/User';

export function getUserRoles(user: User | null | undefined): UserRole[] {
    if (!user) return [];

    const roles: UserRole[] = [];

    if (Array.isArray((user as unknown as { roles?: unknown }).roles)) {
        const rolesArray = (user as unknown as { roles: unknown[] }).roles;
        for (const role of rolesArray) {
            if (role === 'cliente' || role === 'mecanico' || role === 'administrador') {
                if (!roles.includes(role)) roles.push(role);
            }
        }
    }

    if (user.role === 'cliente' || user.role === 'mecanico' || user.role === 'administrador') {
        if (!roles.includes(user.role)) roles.push(user.role);
    }

    return roles;
}

export function hasAnyRole(user: User | null | undefined, ...roles: UserRole[]): boolean {
    if (!user || roles.length === 0) return false;
    const userRoles = getUserRoles(user);
    if (userRoles.length === 0) return false;
    return roles.some((role) => userRoles.includes(role));
}

export function hasAllRoles(user: User | null | undefined, ...roles: UserRole[]): boolean {
    if (!user || roles.length === 0) return false;
    const userRoles = getUserRoles(user);
    if (userRoles.length === 0) return false;
    return roles.every((role) => userRoles.includes(role));
}

export function canAccessRoute(user: User | null | undefined, allowedRoles?: UserRole[]): boolean {
    if (!allowedRoles || allowedRoles.length === 0) return true;
    return hasAnyRole(user, ...allowedRoles);
}

export function canShow(user: User | null | undefined, rolesPermitidos: UserRole[]): boolean {
    if (!rolesPermitidos || rolesPermitidos.length === 0) return true;
    return hasAnyRole(user, ...rolesPermitidos);
}
