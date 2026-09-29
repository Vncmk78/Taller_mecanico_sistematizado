const fs = require('fs');
const path = require('path');

const DB_FILE = path.join(__dirname, 'orders.json');

// Inicializar BD si no existe
if (!fs.existsSync(DB_FILE)) {
  fs.writeFileSync(DB_FILE, JSON.stringify([], null, 2));
}

class OrderDatabase {
  static readDB() {
    try {
      const data = fs.readFileSync(DB_FILE, 'utf-8');
      return JSON.parse(data) || [];
    } catch (error) {
      return [];
    }
  }

  static writeDB(data) {
    fs.writeFileSync(DB_FILE, JSON.stringify(data, null, 2));
  }

  static async create(orderData) {
    const orders = this.readDB();
    const order = {
      id: `ord_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      clienteId: orderData.clienteId,
      mecanicoAsignadoId: orderData.mecanicoAsignadoId || null,
      estado: 'recibido',
      createdAt: new Date(),
      ...orderData
    };
    orders.push(order);
    this.writeDB(orders);
    return order;
  }

  static async findById(id) {
    const orders = this.readDB();
    return orders.find(o => o.id === id);
  }

  static async findByClienteId(clienteId) {
    const orders = this.readDB();
    return orders.filter(o => o.clienteId === clienteId);
  }

  static async findByMecanicoId(mecanicoId) {
    const orders = this.readDB();
    return orders.filter(o => o.mecanicoAsignadoId === mecanicoId);
  }

  static async update(id, updateData) {
    let orders = this.readDB();
    const index = orders.findIndex(o => o.id === id);
    if (index === -1) return null;
    orders[index] = { ...orders[index], ...updateData };
    this.writeDB(orders);
    return orders[index];
  }

  static async getAll() {
    return this.readDB();
  }
}

module.exports = OrderDatabase;
