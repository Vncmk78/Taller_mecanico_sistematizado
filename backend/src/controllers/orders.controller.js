/**
 * TAREA 5: Controlador de órdenes con propiedad de recurso
 * Verifica que el usuario solo accede a sus propios recursos
 */

const OrderDatabase = require('../database/orders.db');

class OrdersController {
  /**
   * Crear nueva orden (solo cliente autenticado)
   */
  static async createOrder(req, res, next) {
    try {
      const { descripcion, vehiculoId } = req.body;
      const clienteId = req.user.id;

      if (!descripcion || !vehiculoId) {
        return res.status(400).json({ 
          error: 'Descripción y vehiculoId son requeridos' 
        });
      }

      const order = await OrderDatabase.create({
        clienteId,
        descripcion,
        vehiculoId
      });

      res.status(201).json({
        message: 'Orden creada exitosamente',
        order
      });
    } catch (error) {
      next(error);
    }
  }

  /**
   * Obtener orden por ID - CON VERIFICACIÓN DE PROPIEDAD
   * El middleware checkOrderOwnership() verifica antes de llegar aquí
   */
  static async getOrderById(req, res, next) {
    try {
      // req.order ya fue validado por checkOrderOwnership()
      res.json({
        message: 'Orden obtenida',
        order: req.order
      });
    } catch (error) {
      next(error);
    }
  }

  /**
   * Obtener mis órdenes (cliente) / órdenes asignadas (mecánico)
   * TAREA 5: Solo ve las SUYAS, no las de otros
   */
  static async getMyOrders(req, res, next) {
    try {
      const userId = req.user.id;
      const userRole = req.user.role;

      let orders;

      if (userRole === 'cliente') {
        // Cliente solo ve SUS órdenes
        orders = await OrderDatabase.findByClienteId(userId);
      } else if (userRole === 'mecanico') {
        // Mecánico solo ve órdenes que le fueron ASIGNADAS
        orders = await OrderDatabase.findByMecanicoId(userId);
      } else if (userRole === 'administrador') {
        // Admin ve TODAS las órdenes
        orders = await OrderDatabase.getAll();
      }

      res.json({
        message: 'Órdenes obtenidas',
        count: orders.length,
        orders
      });
    } catch (error) {
      next(error);
    }
  }

  /**
   * Actualizar orden - CON VERIFICACIÓN DE PROPIEDAD
   */
  static async updateOrder(req, res, next) {
    try {
      const { orderId } = req.params;
      const userRole = req.user.role;
      const updateData = req.body;

      // req.order ya fue validado por checkOrderOwnership()
      const order = req.order;

      // Cliente solo puede actualizar ciertos campos
      if (userRole === 'cliente') {
        // Cliente solo puede comentar, no cambiar estado
        if (updateData.estado || updateData.mecanicoAsignadoId) {
          return res.status(403).json({ 
            error: 'No puedes cambiar el estado o mecánico asignado' 
          });
        }
      }

      // Mecánico solo puede actualizar estado
      if (userRole === 'mecanico') {
        if (updateData.clienteId || updateData.vehiculoId) {
          return res.status(403).json({ 
            error: 'No puedes cambiar cliente o vehículo' 
          });
        }
      }

      const updatedOrder = await OrderDatabase.update(orderId, updateData);

      res.json({
        message: 'Orden actualizada',
        order: updatedOrder
      });
    } catch (error) {
      next(error);
    }
  }

  /**
   * Obtener todas las órdenes (SOLO ADMIN)
   */
  static async getAllOrders(req, res, next) {
    try {
      const orders = await OrderDatabase.getAll();
      res.json({
        message: 'Todas las órdenes',
        count: orders.length,
        orders
      });
    } catch (error) {
      next(error);
    }
  }
}

module.exports = OrdersController;
