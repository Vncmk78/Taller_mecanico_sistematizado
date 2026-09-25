const express = require('express');
const router = express.Router();
const { authMiddleware, requireRole } = require('../middleware/auth.middleware');
const { checkOrderOwnership } = require('../middleware/ownership.middleware');
const OrdersController = require('../controllers/orders.controller');

/**
 * TAREA 5: Rutas de órdenes con verificación de propiedad
 * Cliente solo accede a SUS órdenes
 * Mecánico solo accede a órdenes que le fueron ASIGNADAS
 * Admin accede a TODO
 */

// Crear orden (cliente autenticado)
router.post(
  '/',
  authMiddleware,
  requireRole(['cliente']),
  OrdersController.createOrder
);

// Obtener mis órdenes (cliente/mecanico) o todas (admin)
router.get(
  '/me',
  authMiddleware,
  OrdersController.getMyOrders
);

// Obtener orden específica CON VERIFICACIÓN DE PROPIEDAD
router.get(
  '/:orderId',
  authMiddleware,
  checkOrderOwnership,
  OrdersController.getOrderById
);

// Actualizar orden CON VERIFICACIÓN DE PROPIEDAD
router.patch(
  '/:orderId',
  authMiddleware,
  checkOrderOwnership,
  OrdersController.updateOrder
);

// Obtener todas las órdenes (solo admin)
router.get(
  '/',
  authMiddleware,
  requireRole(['administrador']),
  OrdersController.getAllOrders
);

module.exports = router;
