const User = require('../models/User');
const UserDatabase = require('../database/users.db');
const JWTUtil = require('../utils/jwt.util');
const { BCRYPT_ROUNDS } = require('../config/jwt.config');

class AuthController {
  // TAREA 1: Endpoint de registro de usuario
  static async register(req, res, next) {
    try {
      const { email, password, name, role } = req.body;

      // Validaciones básicas
      if (!email || !password || !name || !role) {
        return res.status(400).json({
          error: 'Faltan campos requeridos: email, password, name, role'
        });
      }

      // Validar email
      if (!User.validateEmail(email)) {
        return res.status(400).json({ 
          error: 'El email no tiene un formato válido' 
        });
      }

      // TAREA 3: Validar contraseña (requisitos de seguridad)
      const passwordValidation = User.validatePassword(password);
      if (!passwordValidation.valid) {
        return res.status(400).json({ 
          error: passwordValidation.message 
        });
      }

      // Validar rol
      const validRoles = ['cliente', 'mecanico', 'administrador'];
      if (!validRoles.includes(role)) {
        return res.status(400).json({ 
          error: `Role debe ser: ${validRoles.join(', ')}` 
        });
      }

      // Verificar que email no existe
      const existingUser = await UserDatabase.findByEmail(email);
      if (existingUser) {
        // TAREA 4: No revelar si el email existe por seguridad
        return res.status(400).json({ 
          error: 'No se puede crear la cuenta con estos datos' 
        });
      }

      // TAREA 3: Hashear contraseña con bcryptjs
      const passwordHash = await User.hashPassword(password, BCRYPT_ROUNDS);

      // Crear usuario
      const user = await UserDatabase.create({
        email: email.toLowerCase(),
        passwordHash,
        name,
        role,
        isActive: true
      });

      // TAREA 1: Generar JWT
      const token = JWTUtil.generateToken({
        id: user.id,
        email: user.email,
        role: user.role
      });

      res.status(201).json({
        message: 'Usuario creado exitosamente',
        user: user.toJSON(),
        token
      });
    } catch (error) {
      next(error);
    }
  }

  // TAREA 1: Endpoint de login/autenticación
  static async login(req, res, next) {
    try {
      const { email, password } = req.body;

      // Validación
      if (!email || !password) {
        return res.status(400).json({ 
          error: 'Email y contraseña son requeridos' 
        });
      }

      // Buscar usuario
      const user = await UserDatabase.findByEmail(email);
      
      // TAREA 4: Si no existe o contraseña inválida, mismo mensaje por seguridad
      if (!user) {
        return res.status(401).json({ 
          error: 'Credenciales inválidas' 
        });
      }

      // TAREA 3: Comparar contraseñas con bcryptjs
      const isPasswordValid = await user.comparePassword(password);
      if (!isPasswordValid) {
        return res.status(401).json({ 
          error: 'Credenciales inválidas' 
        });
      }

      // Verificar que está activo
      if (!user.isActive) {
        return res.status(403).json({ 
          error: 'Usuario desactivado' 
        });
      }

      // TAREA 1: Generar JWT con claims
      const token = JWTUtil.generateToken({
        id: user.id,
        email: user.email,
        role: user.role
      });

      // TAREA 2: Retornar role para autorización
      res.json({
        message: 'Login exitoso',
        user: user.toJSON(),
        token
      });
    } catch (error) {
      next(error);
    }
  }

  // TAREA 1: Endpoint de consulta del usuario autenticado
  static async getProfile(req, res, next) {
    try {
      const user = await UserDatabase.findById(req.user.id);
      
      if (!user) {
        return res.status(404).json({ error: 'Usuario no encontrado' });
      }

      res.json({
        message: 'Perfil obtenido',
        user: user.toJSON()
      });
    } catch (error) {
      next(error);
    }
  }

  // TAREA 1: Endpoint para verificar token
  static async verify(req, res) {
    res.json({
      message: 'Token válido',
      user: req.user
    });
  }

  // TAREA 2: Endpoint para obtener usuarios (solo admin)
  static async getAllUsers(req, res, next) {
    try {
      const users = await UserDatabase.getAll();
      const usersData = users.map(u => u.toJSON());

      res.json({
        message: 'Usuarios obtenidos',
        count: usersData.length,
        users: usersData
      });
    } catch (error) {
      next(error);
    }
  }

  // TAREA 2: Endpoint para obtener usuarios por rol (solo admin)
  static async getUsersByRole(req, res, next) {
    try {
      const { role } = req.params;
      
      const validRoles = ['cliente', 'mecanico', 'administrador'];
      if (!validRoles.includes(role)) {
        return res.status(400).json({ 
          error: `Role debe ser: ${validRoles.join(', ')}` 
        });
      }

      const users = await UserDatabase.getByRole(role);
      const usersData = users.map(u => u.toJSON());

      res.json({
        message: `Usuarios con role: ${role}`,
        count: usersData.length,
        users: usersData
      });
    } catch (error) {
      next(error);
    }
  }

  // Endpoint de logout
  static async logout(req, res) {
    res.json({
      message: 'Logout exitoso'
    });
  }
}

module.exports = AuthController;
