export type UserRole = 'cliente' | 'mecanico' | 'administrador';

export interface User {
  id: string;
  email: string;
  full_name: string;
  /** Rol que define el portal de ingreso (el primero de `roles`). */
  role: UserRole;
  /**
   * Todos los roles de la cuenta. Los roles se acumulan (matriz de autorización
   * §3.1): las guardas de ruta y la visibilidad deben considerar cada uno.
   */
  roles?: UserRole[];
  is_active: boolean;
}

/** Usuario tal como lo lista la API administrativa (puede tener varios roles). */
export interface UsuarioListado {
  id: string;
  email: string;
  full_name: string;
  roles: UserRole[];
  is_active: boolean;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}