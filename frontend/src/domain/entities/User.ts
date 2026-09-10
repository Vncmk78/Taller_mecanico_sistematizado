export interface User {
  id: string;
  email: string;
  name: string;
  roles: Role[];
}

export interface Role {
  id: string;
  name: 'cliente' | 'mecanico' | 'administrador';
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
