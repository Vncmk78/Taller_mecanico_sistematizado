const bcrypt = require('bcryptjs');

class User {
  constructor(data) {
    this.id = data.id || this.generateId();
    this.email = data.email;
    this.passwordHash = data.passwordHash;
    this.name = data.name;
    this.role = data.role; // 'cliente', 'mecanico', 'administrador'
    this.createdAt = data.createdAt || new Date();
    this.isActive = data.isActive !== false;
  }

  generateId() {
    return `usr_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  // Hashea la contraseña usando bcryptjs
  static async hashPassword(password, rounds) {
    return await bcrypt.hash(password, rounds);
  }

  // Compara contraseña en texto plano con el hash
  async comparePassword(plainPassword) {
    return await bcrypt.compare(plainPassword, this.passwordHash);
  }

  // Retorna usuario sin la contraseña
  toJSON() {
    const { passwordHash, ...user } = this;
    return user;
  }

  // Valida el formato del email
  static validateEmail(email) {
    const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return regex.test(email);
  }

  // Valida que la contraseña cumpla requisitos mínimos
  static validatePassword(password) {
    // Mínimo 8 caracteres
    if (password.length < 8) {
      return { valid: false, message: 'Contraseña debe tener al menos 8 caracteres' };
    }
    // Al menos una mayúscula
    if (!/[A-Z]/.test(password)) {
      return { valid: false, message: 'Debe contener al menos una mayúscula' };
    }
    // Al menos un número
    if (!/[0-9]/.test(password)) {
      return { valid: false, message: 'Debe contener al menos un número' };
    }
    return { valid: true };
  }
}

module.exports = User;
