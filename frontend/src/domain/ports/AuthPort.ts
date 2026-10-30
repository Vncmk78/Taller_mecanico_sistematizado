import type { LoginRequest, AuthResponse, User, UsuarioListado } from '../entities/User';

export interface AuthPort {
  login(credentials: LoginRequest): Promise<AuthResponse>;
  getProfile(): Promise<User>;
  /** Lista de usuarios del sistema (solo administrador; GET /auth/usuarios). */
  listarUsuarios(): Promise<UsuarioListado[]>;
}