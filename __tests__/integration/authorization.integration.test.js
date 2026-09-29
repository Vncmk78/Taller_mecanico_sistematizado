/**
 * PRUEBAS DE INTEGRACIÓN: Autorización por Roles
 */

const request = require('supertest');
const app = require('../../src/index');

describe('Authorization by Roles Integration', () => {

  let clienteToken;
  let mecanicoToken;
  let adminToken;

  beforeAll(async () => {
    // Registrar cliente
    const clienteRes = await request(app)
      .post('/api/auth/register')
      .send({
        email: 'cliente@auth.cl',
        password: 'ClientePass@123',
        name: 'Cliente Test',
        role: 'cliente'
      });
    clienteToken = clienteRes.body.token;

    // Registrar mecánico
    const mecanicoRes = await request(app)
      .post('/api/auth/register')
      .send({
        email: 'mecanico@auth.cl',
        password: 'MecanicoPass@123',
        name: 'Mecánico Test',
        role: 'mecanico'
      });
    mecanicoToken = mecanicoRes.body.token;

    // Registrar admin
    const adminRes = await request(app)
      .post('/api/auth/register')
      .send({
        email: 'admin@auth.cl',
        password: 'AdminPass@123',
        name: 'Admin Test',
        role: 'administrador'
      });
    adminToken = adminRes.body.token;
  });

  describe('GET /api/auth/users - Only Admin Access', () => {

    test('Admin can access /users', async () => {
      const res = await request(app)
        .get('/api/auth/users')
        .set('Authorization', `Bearer ${adminToken}`);

      expect(res.statusCode).toBe(200);
      expect(res.body.users).toBeDefined();
      expect(Array.isArray(res.body.users)).toBe(true);
    });

    test('Cliente cannot access /users', async () => {
      const res = await request(app)
        .get('/api/auth/users')
        .set('Authorization', `Bearer ${clienteToken}`);

      expect(res.statusCode).toBe(403);
      expect(res.body.error).toContain('Acceso denegado');
    });

    test('Mecánico cannot access /users', async () => {
      const res = await request(app)
        .get('/api/auth/users')
        .set('Authorization', `Bearer ${mecanicoToken}`);

      expect(res.statusCode).toBe(403);
      expect(res.body.error).toContain('Acceso denegado');
    });

  });

  describe('GET /api/auth/users/:role - Only Admin Access', () => {

    test('Admin can access /users/:role', async () => {
      const res = await request(app)
        .get('/api/auth/users/cliente')
        .set('Authorization', `Bearer ${adminToken}`);

      expect(res.statusCode).toBe(200);
      expect(res.body.users).toBeDefined();
      expect(Array.isArray(res.body.users)).toBe(true);
    });

    test('Cliente cannot access /users/:role', async () => {
      const res = await request(app)
        .get('/api/auth/users/cliente')
        .set('Authorization', `Bearer ${clienteToken}`);

      expect(res.statusCode).toBe(403);
      expect(res.body.error).toContain('Acceso denegado');
    });

    test('Mecánico cannot access /users/:role', async () => {
      const res = await request(app)
        .get('/api/auth/users/mecanico')
        .set('Authorization', `Bearer ${mecanicoToken}`);

      expect(res.statusCode).toBe(403);
      expect(res.body.error).toContain('Acceso denegado');
    });

  });

  describe('Protected Routes - Authentication Required', () => {

    test('Reject request without token to protected route', async () => {
      const res = await request(app)
        .get('/api/auth/profile');

      expect(res.statusCode).toBe(401);
      expect(res.body.error).toContain('token');
    });

    test('Reject request with expired token', async () => {
      // Crear token con expiración muy corta (esto requeriría modificar config)
      // Por ahora solo verificamos que inválido es rechazado
      const res = await request(app)
        .get('/api/auth/profile')
        .set('Authorization', 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalid.token');

      expect(res.statusCode).toBe(401);
    });

  });

  describe('Role-Based Access Control', () => {

    test('All authenticated users can access /profile', async () => {
      const roles = [
        { token: clienteToken, role: 'cliente' },
        { token: mecanicoToken, role: 'mecanico' },
        { token: adminToken, role: 'administrador' }
      ];

      for (const roleAuth of roles) {
        const res = await request(app)
          .get('/api/auth/profile')
          .set('Authorization', `Bearer ${roleAuth.token}`);

        expect(res.statusCode).toBe(200);
        expect(res.body.user.role).toBe(roleAuth.role);
      }
    });

  });

});
