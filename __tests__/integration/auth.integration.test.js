/**
 * PRUEBAS DE INTEGRACIÓN: Endpoints de Autenticación
 */

const request = require('supertest');
const app = require('../../src/index');

describe('Authentication Endpoints Integration', () => {

  let authToken;
  let userId;

  test('POST /api/auth/register - Register new user', async () => {
    const res = await request(app)
      .post('/api/auth/register')
      .send({
        email: 'testuser@test.cl',
        password: 'TestPass@123',
        name: 'Test User',
        role: 'cliente'
      });

    expect(res.statusCode).toBe(201);
    expect(res.body.user).toBeDefined();
    expect(res.body.token).toBeDefined();
    expect(res.body.user.email).toBe('testuser@test.cl');
    expect(res.body.user.role).toBe('cliente');
    expect(res.body.user.passwordHash).toBeUndefined();
    
    userId = res.body.user.id;
  });

  test('POST /api/auth/register - Reject invalid email', async () => {
    const res = await request(app)
      .post('/api/auth/register')
      .send({
        email: 'notanemail',
        password: 'TestPass@123',
        name: 'Test User',
        role: 'cliente'
      });

    expect(res.statusCode).toBe(400);
    expect(res.body.error).toContain('email');
  });

  test('POST /api/auth/register - Reject weak password', async () => {
    const res = await request(app)
      .post('/api/auth/register')
      .send({
        email: 'test2@test.cl',
        password: 'weak',
        name: 'Test User',
        role: 'cliente'
      });

    expect(res.statusCode).toBe(400);
    expect(res.body.error).toContain('contraseña');
  });

  test('POST /api/auth/register - Reject duplicate email', async () => {
    await request(app)
      .post('/api/auth/register')
      .send({
        email: 'duplicate@test.cl',
        password: 'DuplicatePass@123',
        name: 'User 1',
        role: 'cliente'
      });

    const res = await request(app)
      .post('/api/auth/register')
      .send({
        email: 'duplicate@test.cl',
        password: 'DuplicatePass@123',
        name: 'User 2',
        role: 'cliente'
      });

    expect(res.statusCode).toBe(400);
  });

  test('POST /api/auth/login - Login successfully', async () => {
    // Primero registrar
    await request(app)
      .post('/api/auth/register')
      .send({
        email: 'login@test.cl',
        password: 'LoginPass@123',
        name: 'Login User',
        role: 'cliente'
      });

    // Luego login
    const res = await request(app)
      .post('/api/auth/login')
      .send({
        email: 'login@test.cl',
        password: 'LoginPass@123'
      });

    expect(res.statusCode).toBe(200);
    expect(res.body.token).toBeDefined();
    expect(res.body.user).toBeDefined();
    expect(res.body.user.email).toBe('login@test.cl');
    
    authToken = res.body.token;
  });

  test('POST /api/auth/login - Reject wrong password', async () => {
    await request(app)
      .post('/api/auth/register')
      .send({
        email: 'wrongpass@test.cl',
        password: 'CorrectPass@123',
        name: 'Wrong Pass User',
        role: 'cliente'
      });

    const res = await request(app)
      .post('/api/auth/login')
      .send({
        email: 'wrongpass@test.cl',
        password: 'WrongPass@123'
      });

    expect(res.statusCode).toBe(401);
    expect(res.body.error).toContain('Credenciales');
  });

  test('POST /api/auth/login - Generic error for non-existent user', async () => {
    const res = await request(app)
      .post('/api/auth/login')
      .send({
        email: 'nonexistent@test.cl',
        password: 'AnyPass@123'
      });

    expect(res.statusCode).toBe(401);
    expect(res.body.error).toBe('Credenciales inválidas');
  });

  test('GET /api/auth/profile - Get user profile with valid token', async () => {
    const regRes = await request(app)
      .post('/api/auth/register')
      .send({
        email: 'profile@test.cl',
        password: 'ProfilePass@123',
        name: 'Profile User',
        role: 'cliente'
      });

    const res = await request(app)
      .get('/api/auth/profile')
      .set('Authorization', `Bearer ${regRes.body.token}`);

    expect(res.statusCode).toBe(200);
    expect(res.body.user).toBeDefined();
    expect(res.body.user.email).toBe('profile@test.cl');
    expect(res.body.user.passwordHash).toBeUndefined();
  });

  test('GET /api/auth/profile - Reject missing token', async () => {
    const res = await request(app)
      .get('/api/auth/profile');

    expect(res.statusCode).toBe(401);
    expect(res.body.error).toContain('token');
  });

  test('GET /api/auth/profile - Reject invalid token', async () => {
    const res = await request(app)
      .get('/api/auth/profile')
      .set('Authorization', 'Bearer invalid.token.here');

    expect(res.statusCode).toBe(401);
    expect(res.body.error).toContain('Token');
  });

  test('GET /api/auth/verify - Verify valid token', async () => {
    const regRes = await request(app)
      .post('/api/auth/register')
      .send({
        email: 'verify@test.cl',
        password: 'VerifyPass@123',
        name: 'Verify User',
        role: 'cliente'
      });

    const res = await request(app)
      .get('/api/auth/verify')
      .set('Authorization', `Bearer ${regRes.body.token}`);

    expect(res.statusCode).toBe(200);
    expect(res.body.user).toBeDefined();
    expect(res.body.message).toContain('válido');
  });

});
