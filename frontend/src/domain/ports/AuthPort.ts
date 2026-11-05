import type { LoginRequest, AuthResponse, RegisterRequest, User, UsuarioListado } from '../entities/User';

export interface AuthPort {
  /** Registro público: crea solo una cuenta Cliente (POST /auth/register). */
  register(data: RegisterRequest): Promise<User>;
  login(credentials: LoginRequest): Promise<AuthResponse>;
  getProfile(): Promise<User>;
  /** Lista de usuarios del sistema (solo administrador; GET /auth/usuarios). */
  listarUsuarios(): Promise<UsuarioListado[]>;
}