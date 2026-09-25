const JWTUtil = require('../utils/jwt.util');

// Middleware de autenticación - verifica que el token sea válido
const authMiddleware = (req, res, next) => {
  try {
    const authHeader = req.headers.authorization;
    const token = JWTUtil.extractTokenFromHeader(authHeader);
    const decoded = JWTUtil.verifyToken(token);
    
    // Guardar en el request
    req.user = decoded;
    req.token = token;
    
    next();
  } catch (error) {
    console.error('[AUTH ERROR]', error.message);
    res.status(error.status || 401).json({ 
      error: error.message
    });
  }
};

// Middleware de autorización por rol
const requireRole = (allowedRoles) => {
  return (req, res, next) => {
    if (!req.user) {
      return res.status(401).json({ error: 'Usuario no autenticado' });
    }

    if (!allowedRoles.includes(req.user.role)) {
      return res.status(403).json({ 
        error: `Acceso denegado para role ${req.user.role}` 
      });
    }

    next();
  };
};

module.exports = {
  authMiddleware,
  requireRole
};
