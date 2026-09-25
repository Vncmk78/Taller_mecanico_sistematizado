const jwt = require('jsonwebtoken');
const { JWT_SECRET, JWT_EXPIRE } = require('../config/jwt.config');

class JWTUtil {
  // Genera un nuevo token
  static generateToken(payload) {
    try {
      return jwt.sign(payload, JWT_SECRET, { 
        expiresIn: JWT_EXPIRE,
        algorithm: 'HS256'
      });
    } catch (error) {
      throw { status: 500, message: 'Error generando token' };
    }
  }

  // Verifica que el token sea válido
  static verifyToken(token) {
    try {
      return jwt.verify(token, JWT_SECRET);
    } catch (error) {
      if (error.name === 'TokenExpiredError') {
        throw { status: 401, message: 'Token expirado' };
      }
      throw { status: 401, message: 'Token inválido' };
    }
  }

  // Extrae el token del header Authorization
  static extractTokenFromHeader(authHeader) {
    if (!authHeader) {
      throw { status: 401, message: 'No se proporcionó token' };
    }

    if (!authHeader.startsWith('Bearer ')) {
      throw { status: 401, message: 'Formato Authorization inválido' };
    }

    return authHeader.substring(7);
  }
}

module.exports = JWTUtil;
