/**
 * PRUEBAS UNITARIAS: User Model
 */

const User = require('../../src/models/User');
const bcrypt = require('bcryptjs');

describe('User Model - Validation and Hashing', () => {

  test('Validate correct email format', () => {
    const validEmail = 'test@example.com';
    expect(User.validateEmail(validEmail)).toBe(true);
  });

  test('Reject invalid email format', () => {
    const invalidEmails = [
      'notanemail',
      'missing@domain',
      '@nodomain.com',
      'spaces in@email.com'
    ];
    
    invalidEmails.forEach(email => {
      expect(User.validateEmail(email)).toBe(false);
    });
  });

  test('Validate password with correct requirements', () => {
    const validPassword = 'Password@123';
    const result = User.validatePassword(validPassword);
    
    expect(result.valid).toBe(true);
  });

  test('Reject password too short', () => {
    const shortPassword = 'Pass@1';
    const result = User.validatePassword(shortPassword);
    
    expect(result.valid).toBe(false);
    expect(result.message).toContain('8');
  });

  test('Reject password without uppercase', () => {
    const noUppercase = 'password@123';
    const result = User.validatePassword(noUppercase);
    
    expect(result.valid).toBe(false);
    expect(result.message).toContain('mayúscula');
  });

  test('Reject password without number', () => {
    const noNumber = 'Password@abc';
    const result = User.validatePassword(noNumber);
    
    expect(result.valid).toBe(false);
    expect(result.message).toContain('número');
  });

  test('Hash password correctly', async () => {
    const plainPassword = 'Password@123';
    const hash = await User.hashPassword(plainPassword, 10);
    
    expect(hash).toBeTruthy();
    expect(hash).not.toBe(plainPassword);
    expect(hash).toMatch(/^\$2[aby]\$/); // bcrypt format
  });

  test('Compare passwords correctly', async () => {
    const plainPassword = 'Password@123';
    const hash = await User.hashPassword(plainPassword, 10);
    
    const user = new User({
      id: 'usr_123',
      email: 'test@test.cl',
      passwordHash: hash,
      name: 'Test',
      role: 'cliente'
    });
    
    const isValid = await user.comparePassword(plainPassword);
    expect(isValid).toBe(true);
  });

  test('Reject wrong password', async () => {
    const plainPassword = 'Password@123';
    const wrongPassword = 'WrongPass@456';
    const hash = await User.hashPassword(plainPassword, 10);
    
    const user = new User({
      id: 'usr_123',
      email: 'test@test.cl',
      passwordHash: hash,
      name: 'Test',
      role: 'cliente'
    });
    
    const isValid = await user.comparePassword(wrongPassword);
    expect(isValid).toBe(false);
  });

  test('User toJSON does not include password', async () => {
    const hash = await User.hashPassword('Password@123', 10);
    const user = new User({
      id: 'usr_123',
      email: 'test@test.cl',
      passwordHash: hash,
      name: 'Test',
      role: 'cliente'
    });
    
    const userJSON = user.toJSON();
    expect(userJSON.passwordHash).toBeUndefined();
    expect(userJSON.id).toBe('usr_123');
    expect(userJSON.email).toBe('test@test.cl');
  });

});
