import type { AuthResponse, LoginRequest, User } from '@/domain/entities/User';
import type { AuthPort } from '@/domain/ports/AuthPort';
import apiClient from '../config/apiClient';

class AuthService implements AuthPort {
  async login(credentials: LoginRequest): Promise<AuthResponse> {
    const { data } = await apiClient.post<AuthResponse>('/auth/login', credentials);
    return data;
  }

  async getProfile(): Promise<User> {
    const { data } = await apiClient.get<User>('/auth/me');
    return data;
  }
}

export const authService = new AuthService();