/**
 * PRUEBAS UNITARIAS: JWT Utilities
 */

const JWTUtil = require('../../src/utils/jwt.util');

describe('JWTUtil - JWT Generation and Verification', () => {
  
  test('Generate token with correct payload', () => {
    const payload = { id: 'usr_123', email: 'test@test.cl', role: 'cliente' };
    const token = JWTUtil.generateToken(payload);
    
    expect(token).toBeTruthy();
    expect(typeof token).toBe('string');
    expect(token.split('.').length).toBe(3); // JWT tiene 3 partes
  });

  test('Verify valid token', () => {
    const payload = { id: 'usr_123', email: 'test@test.cl', role: 'cliente' };
    const token = JWTUtil.generateToken(payload);
    const decoded = JWTUtil.verifyToken(token);
    
    expect(decoded.id).toBe('usr_123');
    expect(decoded.email).toBe('test@test.cl');
    expect(decoded.role).toBe('cliente');
  });

  test('Reject invalid token', () => {
    const invalidToken = 'token.falso.123';
    
    expect(() => {
      JWTUtil.verifyToken(invalidToken);
    }).toThrow();
  });

  test('Extract token from Authorization header', () => {
    const payload = { id: 'usr_123', email: 'test@test.cl', role: 'cliente' };
    const token = JWTUtil.generateToken(payload);
    const authHeader = `Bearer ${token}`;
    
    const extracted = JWTUtil.extractTokenFromHeader(authHeader);
    expect(extracted).toBe(token);
  });

  test('Reject header without Bearer prefix', () => {
    const authHeader = 'eyJhbGciOiJIUzI1NiIs...';
    
    expect(() => {
      JWTUtil.extractTokenFromHeader(authHeader);
    }).toThrow();
  });

  test('Reject missing Authorization header', () => {
    expect(() => {
      JWTUtil.extractTokenFromHeader(undefined);
    }).toThrow();
  });

  test('Decode token without verification', () => {
    const payload = { id: 'usr_123', email: 'test@test.cl', role: 'cliente' };
    const token = JWTUtil.generateToken(payload);
    const decoded = JWTUtil.decodeToken(token);
    
    expect(decoded.id).toBe('usr_123');
    expect(decoded.email).toBe('test@test.cl');
  });

  test('Token contains expiration claim', () => {
    const payload = { id: 'usr_123', email: 'test@test.cl', role: 'cliente' };
    const token = JWTUtil.generateToken(payload);
    const decoded = JWTUtil.decodeToken(token);
    
    expect(decoded.exp).toBeTruthy();
    expect(typeof decoded.exp).toBe('number');
  });

});
