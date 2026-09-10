import type { LoginRequest, AuthResponse } from '../entities/User';

export interface AuthPort {
  login(credentials: LoginRequest): Promise<AuthResponse>;
  logout(): void;
  getProfile(): Promise<AuthResponse['user']>;
}
