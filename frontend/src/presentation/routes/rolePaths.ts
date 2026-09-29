import type { UserRole } from '@/domain/entities/User';

export const homeByRole: Record<UserRole, string> = {
  administrador: '/admin',
  cliente: '/client',
  mecanico: '/mechanic',
};

export function getHomePath(role: UserRole | undefined): string {
  if (role) return homeByRole[role];
  return '/login';
}