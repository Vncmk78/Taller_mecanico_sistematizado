const User = require('../models/User');
const fs = require('fs');
const path = require('path');

const DB_FILE = path.join(__dirname, 'users.json');

// Inicializar BD si no existe
if (!fs.existsSync(DB_FILE)) {
  fs.writeFileSync(DB_FILE, JSON.stringify([], null, 2));
}

class UserDatabase {
  static readDB() {
    const data = fs.readFileSync(DB_FILE, 'utf-8');
    return JSON.parse(data) || [];
  }

  static writeDB(data) {
    fs.writeFileSync(DB_FILE, JSON.stringify(data, null, 2));
  }

  static async create(userData) {
    const users = this.readDB();
    const user = new User(userData);
    users.push({
      id: user.id,
      email: user.email,
      passwordHash: user.passwordHash,
      name: user.name,
      role: user.role,
      isActive: user.isActive,
      createdAt: user.createdAt
    });
    this.writeDB(users);
    return user;
  }

  static async findByEmail(email) {
    const users = this.readDB();
    const userData = users.find(u => u.email === email.toLowerCase());
    if (!userData) return null;
    return new User(userData);
  }

  static async findById(id) {
    const users = this.readDB();
    const userData = users.find(u => u.id === id);
    if (!userData) return null;
    return new User(userData);
  }

  static async getAll() {
    const users = this.readDB();
    return users.map(u => new User(u));
  }

  static async getByRole(role) {
    const users = this.readDB();
    return users.filter(u => u.role === role).map(u => new User(u));
  }
}

module.exports = UserDatabase;
