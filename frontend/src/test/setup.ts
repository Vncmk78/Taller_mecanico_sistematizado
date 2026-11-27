import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach, beforeEach } from 'vitest';

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
  for (const entrada of document.cookie.split(';')) {
    const nombre = entrada.split('=')[0]?.trim();
    if (nombre) document.cookie = `${nombre}=; Path=/; Max-Age=0`;
  }
});

afterEach(() => {
  cleanup();
});
