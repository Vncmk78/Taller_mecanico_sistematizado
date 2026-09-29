/**
 * PRUEBAS DE INTEGRACIÓN: Propiedad de Recursos
 */

const request = require('supertest');
const app = require('../../src/index');

describe('Resource Ownership Integration', () => {

  let cliente1Token;
  let cliente1Id;
  let cliente2Token;
  let cliente2Id;
  let mecanicoToken;
  let adminToken;
  let orden1Id;

  beforeAll(async () => {
    // Cliente 1
    const c1Res = await request(app)
      .post('/api/auth/register')
      .send({
        email: 'cliente1.own@test.cl',
        password: 'Cliente1@123',
        name: 'Cliente 1',
        role: 'cliente'
      });
    cliente1Token = c1Res.body.token;
    cliente1Id = c1Res.body.user.id;

    // Cliente 2
    const c2Res = await request(app)
      .post('/api/auth/register')
      .send({
        email: 'cliente2.own@test.cl',
        password: 'Cliente2@123',
        name: 'Cliente 2',
        role: 'cliente'
      });
    cliente2Token = c2Res.body.token;
    cliente2Id = c2Res.body.user.id;

    // Mecánico
    const mecRes = await request(app)
      .post('/api/auth/register')
      .send({
        email: 'mecanico.own@test.cl',
        password: 'Mecanico@123',
        name: 'Mecánico',
        role: 'mecanico'
      });
    mecanicoToken = mecRes.body.token;

    // Admin
    const adRes = await request(app)
      .post('/api/auth/register')
      .send({
        email: 'admin.own@test.cl',
        password: 'Admin@123',
        name: 'Admin',
        role: 'administrador'
      });
    adminToken = adRes.body.token;

    // Crear orden como cliente1
    const ordenRes = await request(app)
      .post('/api/orders')
      .set('Authorization', `Bearer ${cliente1Token}`)
      .send({
        descripcion: 'Cambio de aceite',
        vehiculoId: 'veh_001'
      });
    orden1Id = ordenRes.body.order.id;
  });

  describe('Cliente Access to Own Orders', () => {

    test('Cliente can access their own order', async () => {
      const res = await request(app)
        .get(`/api/orders/${orden1Id}`)
        .set('Authorization', `Bearer ${cliente1Token}`);

      expect(res.statusCode).toBe(200);
      expect(res.body.order).toBeDefined();
      expect(res.body.order.clienteId).toBe(cliente1Id);
    });

    test('Cliente cannot access another clients order', async () => {
      const res = await request(app)
        .get(`/api/orders/${orden1Id}`)
        .set('Authorization', `Bearer ${cliente2Token}`);

      expect(res.statusCode).toBe(403);
      expect(res.body.error).toContain('No tienes permiso');
    });

  });

  describe('Cliente See Only Their Orders', () => {

    test('Cliente sees only their own orders', async () => {
      const res = await request(app)
        .get('/api/orders/me')
        .set('Authorization', `Bearer ${cliente1Token}`);

      expect(res.statusCode).toBe(200);
      expect(res.body.orders).toBeDefined();
      expect(Array.isArray(res.body.orders)).toBe(true);
      
      // Todos los órdenes deben pertenecer a este cliente
      res.body.orders.forEach(order => {
        expect(order.clienteId).toBe(cliente1Id);
      });
    });

  });

  describe('Admin Can Access Any Order', () => {

    test('Admin can access any order', async () => {
      const res = await request(app)
        .get(`/api/orders/${orden1Id}`)
        .set('Authorization', `Bearer ${adminToken}`);

      expect(res.statusCode).toBe(200);
      expect(res.body.order).toBeDefined();
    });

    test('Admin can see all orders', async () => {
      const res = await request(app)
        .get('/api/orders')
        .set('Authorization', `Bearer ${adminToken}`);

      expect(res.statusCode).toBe(200);
      expect(res.body.orders).toBeDefined();
      expect(Array.isArray(res.body.orders)).toBe(true);
    });

  });

  describe('Mecánico Access to Assigned Orders', () => {

    test('Mecánico cannot access order not assigned to them', async () => {
      const res = await request(app)
        .get(`/api/orders/${orden1Id}`)
        .set('Authorization', `Bearer ${mecanicoToken}`);

      expect(res.statusCode).toBe(403);
      expect(res.body.error).toContain('no te fue asignada');
    });

  });

  describe('Cross-Access Prevention', () => {

    test('Cliente cannot update order of another client', async () => {
      const res = await request(app)
        .patch(`/api/orders/${orden1Id}`)
        .set('Authorization', `Bearer ${cliente2Token}`)
        .send({ estado: 'completado' });

      expect(res.statusCode).toBe(403);
    });

    test('Mecánico cannot update order not assigned', async () => {
      const res = await request(app)
        .patch(`/api/orders/${orden1Id}`)
        .set('Authorization', `Bearer ${mecanicoToken}`)
        .send({ estado: 'en_proceso' });

      expect(res.statusCode).toBe(403);
    });

    test('Admin can update any order', async () => {
      const res = await request(app)
        .patch(`/api/orders/${orden1Id}`)
        .set('Authorization', `Bearer ${adminToken}`)
        .send({ estado: 'en_revision' });

      expect(res.statusCode).toBe(200);
      expect(res.body.order.estado).toBe('en_revision');
    });

  });

});
