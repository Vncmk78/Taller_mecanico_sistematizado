import type { AuthResponse, LoginRequest, User, UserRole } from '@/domain/entities/User';
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

function toDomainUser(apiUser: ApiUser): User {
  const role = (apiUser.roles?.[0] ?? 'cliente') as UserRole;
  return {
    id: String(apiUser.id),
    email: apiUser.email,
    full_name: apiUser.full_name,
    role,
    is_active: apiUser.is_active,
  };
}

class AuthService implements AuthPort {
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
}

export const authService = new AuthService();