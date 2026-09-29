import type { LoginRequest, AuthResponse, User } from '../entities/User';

export interface AuthPort {
  login(credentials: LoginRequest): Promise<AuthResponse>;
  getProfile(): Promise<User>;
}