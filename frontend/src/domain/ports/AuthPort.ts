import type { LoginRequest, AuthResponse, RegisterRequest, User, UserRole, UsuarioListado } from '../entities/User';

export interface AuthPort {
  /** Registro público: crea solo una cuenta Cliente (POST /auth/register). */
  register(data: RegisterRequest): Promise<User>;
  login(credentials: LoginRequest): Promise<AuthResponse>;
  getProfile(): Promise<User>;
  /** Lista de usuarios del sistema (solo administrador; GET /auth/usuarios). */
  listarUsuarios(): Promise<UsuarioListado[]>;
  /**
   * Agrega un rol a una cuenta (solo Administrador;
   * POST /auth/usuarios/{id}/roles). Es idempotente y devuelve el usuario
   * actualizado. Los roles se acumulan: asignar no quita los existentes.
   */
  asignarRol(usuarioId: string, rol: UserRole): Promise<UsuarioListado>;
  /**
   * Quita un rol de una cuenta (solo Administrador;
   * DELETE /auth/usuarios/{id}/roles/{rol}). Es idempotente y admite dejar la
   * lista vacía, que la cuenta quedaría sin acceso a ningún portal.
   */
  retirarRol(usuarioId: string, rol: UserRole): Promise<UsuarioListado>;
}