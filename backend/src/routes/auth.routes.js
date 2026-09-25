const express = require('express');
const router = express.Router();
const { authMiddleware, requireRole } = require('../middleware/auth.middleware');
const AuthController = require('../controllers/auth.controller');

// TAREA 1: Rutas públicas de autenticación

// Registro de usuario
router.post('/register', AuthController.register);

// Login / Autenticación
router.post('/login', AuthController.login);

// TAREA 1: Rutas protegidas - requieren autenticación

// Obtener perfil del usuario autenticado
router.get('/profile', authMiddleware, AuthController.getProfile);

// Verificar token válido
router.get('/verify', authMiddleware, AuthController.verify);

// Logout
router.post('/logout', authMiddleware, AuthController.logout);

// TAREA 2: Rutas con autorización por rol (solo admin)

// Obtener todos los usuarios (solo administrador)
router.get(
  '/users',
  authMiddleware,
  requireRole(['administrador']),
  AuthController.getAllUsers
);

// Obtener usuarios por rol (solo administrador)
router.get(
  '/users/:role',
  authMiddleware,
  requireRole(['administrador']),
  AuthController.getUsersByRole
);

module.exports = router;
