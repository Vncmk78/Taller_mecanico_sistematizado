/**
 * TAREA 5: Middleware de propiedad de recurso
 * Verifica que el usuario es el propietario del recurso
 */

const OrderDatabase = require('../database/orders.db');

/**
 * Middleware: Verifica que el usuario es propietario de la orden
 * Solo el cliente que creó la orden o un admin pueden acceder
 */
const checkOrderOwnership = async (req, res, next) => {
  try {
    const { orderId } = req.params;
    const userId = req.user.id;
    const userRole = req.user.role;

    // Admin puede acceder a todo
    if (userRole === 'administrador') {
      return next();
    }

    // Buscar la orden
    const order = await OrderDatabase.findById(orderId);
    if (!order) {
      return res.status(404).json({ error: 'Orden no encontrada' });
    }

    // Cliente solo puede acceder a sus propias órdenes
    if (userRole === 'cliente') {
      if (order.clienteId !== userId) {
        return res.status(403).json({ 
          error: 'No tienes permiso para acceder a esta orden' 
        });
      }
    }

    // Mecánico solo puede acceder a órdenes que le fueron asignadas
    if (userRole === 'mecanico') {
      if (order.mecanicoAsignadoId !== userId) {
        return res.status(403).json({ 
          error: 'Esta orden no te fue asignada' 
        });
      }
    }

    // Pasar la orden al siguiente middleware
    req.order = order;
    next();
  } catch (error) {
    console.error('[OWNERSHIP ERROR]', error.message);
    res.status(500).json({ error: 'Error verificando propiedad' });
  }
};

/**
 * Middleware: Verifica que el usuario es propietario del vehículo
 * Solo el cliente propietario o admin pueden acceder
 */
const checkVehicleOwnership = async (req, res, next) => {
  try {
    const { vehicleId } = req.params;
    const userId = req.user.id;
    const userRole = req.user.role;

    // Admin puede acceder a todo
    if (userRole === 'administrador') {
      return next();
    }

    // Solo clientes pueden tener vehículos propios
    if (userRole !== 'cliente') {
      return res.status(403).json({ 
        error: 'Solo clientes pueden tener vehículos propios' 
      });
    }

    // Buscar vehículo (simulado)
    const vehicle = await VehicleDatabase.findById(vehicleId);
    if (!vehicle) {
      return res.status(404).json({ error: 'Vehículo no encontrado' });
    }

    // Verificar propiedad
    if (vehicle.clienteId !== userId) {
      return res.status(403).json({ 
        error: 'Este vehículo no te pertenece' 
      });
    }

    req.vehicle = vehicle;
    next();
  } catch (error) {
    console.error('[OWNERSHIP ERROR]', error.message);
    res.status(500).json({ error: 'Error verificando propiedad' });
  }
};

module.exports = {
  checkOrderOwnership,
  checkVehicleOwnership
};
