import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { User } from '@/domain/entities/User';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { AuthProvider } from '@/presentation/components/auth/AuthProvider';
import { AppRoutes } from '@/presentation/routes/AppRoutes';

vi.mock('@/infrastructure/api/AuthService', () => ({
  authService: {
    login: vi.fn(),
    getProfile: vi.fn(() => new Promise<never>(() => {})),
  },
}));

const adminUser: User = {
  id: '1',
  email: 'admin@taller.cl',
  full_name: 'Admin Test',
  role: 'administrador',
  is_active: true,
};

const clientUser: User = {
  id: '2',
  email: 'cliente@taller.cl',
  full_name: 'Cliente Test',
  role: 'cliente',
  is_active: true,
};

const mechanicUser: User = {
  id: '3',
  email: 'mecanico@taller.cl',
  full_name: 'Mecánico Test',
  role: 'mecanico',
  is_active: true,
};

beforeEach(() => {
  localStorage.clear();
  useAuthStore.setState({
    user: null,
    token: null,
    isAuthenticated: false,
    isLoading: false,
    isInitializing: false,
  });
});

function logueadoComo(user: User) {
  useAuthStore.setState({
    user,
    token: `token-${user.role}`,
    isAuthenticated: true,
    isLoading: false,
    isInitializing: false,
  });
}

function renderApp(entry: string) {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </MemoryRouter>
  );
}

describe('AppRoutes: navegación por los tres roles', () => {
  describe('sin sesión', () => {
    it.each(['/admin', '/client', '/mechanic'])(
      'redirige a /login desde %s',
      (entry) => {
        renderApp(entry);

        expect(
          screen.getByRole('heading', { name: 'Iniciar Sesión' })
        ).toBeInTheDocument();
      }
    );

    it('una ruta inexistente cae en el home', () => {
      renderApp('/ruta-inexistente');

      expect(
        screen.getByText('¿Por qué elegir nuestro sistema?')
      ).toBeInTheDocument();
    });
  });

  describe('portal administrador', () => {
    it('permite entrar a /admin y ver el panel', () => {
      logueadoComo(adminUser);
      renderApp('/admin');

      expect(screen.getByText('Portal Administrador')).toBeInTheDocument();
      expect(
        screen.getByRole('heading', { name: 'Panel de Control Global' })
      ).toBeInTheDocument();
    });

    it('navega con un clic del menú hacia /admin/vehiculos', async () => {
      logueadoComo(adminUser);
      renderApp('/admin');

      fireEvent.click(screen.getByRole('link', { name: 'Vehículos' }));

      expect(
        await screen.findByText('Catálogo de vehículos del taller')
      ).toBeInTheDocument();
    });

    it('niega /admin a un cliente y lo redirige a su portal', () => {
      logueadoComo(clientUser);
      renderApp('/admin');

      expect(screen.getByText('Portal Cliente')).toBeInTheDocument();
      expect(
        screen.queryByRole('heading', { name: 'Panel de Control Global' })
      ).not.toBeInTheDocument();
    });

    it('niega /admin a un mecánico y lo redirige a su portal', () => {
      logueadoComo(mechanicUser);
      renderApp('/admin');

      expect(screen.getByText('Actualizar Estados')).toBeInTheDocument();
      expect(
        screen.queryByRole('heading', { name: 'Panel de Control Global' })
      ).not.toBeInTheDocument();
    });
  });

  describe('portal cliente', () => {
    it('permite entrar a /client y ver mi portal', () => {
      logueadoComo(clientUser);
      renderApp('/client');

      expect(
        screen.getByRole('heading', { name: 'Mi Portal' })
      ).toBeInTheDocument();
      expect(screen.getByText('Mis Vehículos')).toBeInTheDocument();
    });

    it('navega con un clic del menú hacia /client/vehiculos', async () => {
      logueadoComo(clientUser);
      renderApp('/client');

      fireEvent.click(screen.getByRole('link', { name: 'Mis Vehículos' }));

      expect(
        await screen.findByText('Consulta los vehículos registrados a tu nombre')
      ).toBeInTheDocument();
    });

    it('niega /client a un administrador y lo redirige a su panel', () => {
      logueadoComo(adminUser);
      renderApp('/client');

      expect(
        screen.getByRole('heading', { name: 'Panel de Control Global' })
      ).toBeInTheDocument();
      expect(screen.queryByText('Portal Cliente')).not.toBeInTheDocument();
    });

    it('niega /client a un mecánico y lo redirige a su portal', () => {
      logueadoComo(mechanicUser);
      renderApp('/client');

      expect(screen.getByText('Actualizar Estados')).toBeInTheDocument();
      expect(screen.queryByText('Portal Cliente')).not.toBeInTheDocument();
    });
  });

  describe('portal mecánico', () => {
    it('permite entrar a /mechanic y ver mi panel', () => {
      logueadoComo(mechanicUser);
      renderApp('/mechanic');

      expect(
        screen.getByRole('heading', { name: 'Mi Panel' })
      ).toBeInTheDocument();
      expect(screen.getByText('Actualizar Estados')).toBeInTheDocument();
    });

    it('navega con un clic del menú hacia /mechanic/ordenes', async () => {
      logueadoComo(mechanicUser);
      renderApp('/mechanic');

      fireEvent.click(screen.getByRole('link', { name: 'Mis Órdenes' }));

      expect(
        await screen.findByText('Órdenes de trabajo asignadas a tu cuenta')
      ).toBeInTheDocument();
    });

    it('niega /mechanic a un administrador y lo redirige a su panel', () => {
      logueadoComo(adminUser);
      renderApp('/mechanic');

      expect(
        screen.getByRole('heading', { name: 'Panel de Control Global' })
      ).toBeInTheDocument();
      expect(screen.queryByText('Actualizar Estados')).not.toBeInTheDocument();
    });

    it('niega /mechanic a un cliente y lo redirige a su portal', () => {
      logueadoComo(clientUser);
      renderApp('/mechanic');

      expect(screen.getByText('Portal Cliente')).toBeInTheDocument();
      expect(screen.queryByText('Actualizar Estados')).not.toBeInTheDocument();
    });
  });
});