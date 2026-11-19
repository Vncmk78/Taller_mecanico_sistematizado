import type {
  AuthResponse,
  LoginRequest,
  RegisterRequest,
  User,
  UserRole,
  UsuarioListado,
} from '@/domain/entities/User';
import type { AuthPort } from '@/domain/ports/AuthPort';
import apiClient from '../config/apiClient';

interface ApiUser {
  id: number;
  email: string;
  full_name: string;
  roles: string[];
  is_active: boolean;
}

interface ApiAuthResponse {
  access_token: string;
  token_type: string;
  user: ApiUser;
}

const ROLES_VALIDOS: readonly UserRole[] = ['cliente', 'mecanico', 'administrador'];

function esRolValido(rol: string): rol is UserRole {
  return (ROLES_VALIDOS as readonly string[]).includes(rol);
}

// `roles` es una lista y los roles se acumulan: se conservan todos para que las
// guardas (getUserRoles / hasAnyRole) den acceso a cada portal de la cuenta. El
// primero sigue definiendo el portal de ingreso (diferencia D-03).
function toDomainUser(apiUser: ApiUser): User {
  const roles = (apiUser.roles ?? []).filter(esRolValido);
  const role = roles[0] ?? 'cliente';
  return {
    id: String(apiUser.id),
    email: apiUser.email,
    full_name: apiUser.full_name,
    role,
    roles: roles.length > 0 ? roles : [role],
    is_active: apiUser.is_active,
  };
}

/**
 * Usuario del listado administrativo. A diferencia de la sesión, aquí una
 * lista vacía de roles es válida (la cuenta existe pero no accede a ningún
 * portal) y no se rellena con un rol por defecto.
 */
function toUsuarioListado(apiUser: ApiUser): UsuarioListado {
  return {
    id: String(apiUser.id),
    email: apiUser.email,
    full_name: apiUser.full_name,
    roles: (apiUser.roles ?? []).filter(esRolValido),
    is_active: apiUser.is_active,
  };
}

class AuthService implements AuthPort {
  async register(data: RegisterRequest): Promise<User> {
    // Solo se envían los tres campos del contrato: MS1 asigna el rol Cliente y
    // responde 422 ante cualquier campo extra (por ejemplo, un rol).
    const { data: usuario } = await apiClient.post<ApiUser>('/auth/register', {
      email: data.email,
      password: data.password,
      full_name: data.full_name,
    });
    return toDomainUser(usuario);
  }

  async login(credentials: LoginRequest): Promise<AuthResponse> {
    const { data } = await apiClient.post<ApiAuthResponse>('/auth/login', credentials);
    return {
      access_token: data.access_token,
      token_type: data.token_type,
      user: toDomainUser(data.user),
    };
  }

  async getProfile(): Promise<User> {
    const { data } = await apiClient.get<ApiUser>('/auth/me');
    return toDomainUser(data);
  }

  async listarUsuarios(): Promise<UsuarioListado[]> {
    const { data } = await apiClient.get<ApiUser[]>('/auth/usuarios');
    return data.map(toUsuarioListado);
  }

  async asignarRol(usuarioId: string, rol: UserRole): Promise<UsuarioListado> {
    const { data } = await apiClient.post<ApiUser>(`/auth/usuarios/${usuarioId}/roles`, {
      rol,
    });
    return toUsuarioListado(data);
  }

  async retirarRol(usuarioId: string, rol: UserRole): Promise<UsuarioListado> {
    const { data } = await apiClient.delete<ApiUser>(
      `/auth/usuarios/${usuarioId}/roles/${rol}`
    );
    return toUsuarioListado(data);
  }
}

export const authService = new AuthService();