import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { User } from '@/domain/entities/User';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { AuthProvider } from '@/presentation/components/auth/AuthProvider';
import { ToastProvider } from '@/presentation/components/ui/ToastProvider';
import { AppRoutes } from '@/presentation/routes/AppRoutes';

vi.mock('@/infrastructure/api/AuthService', () => ({
  authService: {
    login: vi.fn(),
    getProfile: vi.fn(() => new Promise<never>(() => {})),
    listarUsuarios: vi.fn(() => Promise.resolve([])),
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
        <ToastProvider>
          <AppRoutes />
        </ToastProvider>
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
    const rutasPanelAdmin = [
      '/admin',
      '/admin/ordenes',
      '/admin/ordenes/101',
      '/admin/ordenes/101/evidencias',
      '/admin/clientes',
      '/admin/vehiculos',
      '/admin/vehiculos/7',
      '/admin/inventario',
      '/admin/distribuidores',
    ];

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
        await screen.findByText('Catálogo de Vehículos Registrados')
      ).toBeInTheDocument();
    });

    it('niega /admin a un cliente y lo lleva a acceso denegado', () => {
      logueadoComo(clientUser);
      renderApp('/admin');

      expect(
        screen.getByRole('heading', { name: 'Acceso Denegado' })
      ).toBeInTheDocument();
      expect(
        screen.queryByRole('heading', { name: 'Panel de Control Global' })
      ).not.toBeInTheDocument();
    });

    it('niega /admin a un mecánico y lo lleva a acceso denegado', () => {
      logueadoComo(mechanicUser);
      renderApp('/admin');

      expect(
        screen.getByRole('heading', { name: 'Acceso Denegado' })
      ).toBeInTheDocument();
      expect(
        screen.queryByRole('heading', { name: 'Panel de Control Global' })
      ).not.toBeInTheDocument();
    });

    it.each(rutasPanelAdmin)(
      'sin sesión redirige %s a /login (panel solo accesible por administradores)',
      (entry) => {
        renderApp(entry);

        expect(
          screen.getByRole('heading', { name: 'Iniciar Sesión' })
        ).toBeInTheDocument();
        expect(
          screen.queryByText('Portal Administrador')
        ).not.toBeInTheDocument();
        expect(
          screen.queryByRole('heading', { name: 'Acceso Denegado' })
        ).not.toBeInTheDocument();
      }
    );

    it.each(rutasPanelAdmin)(
      'cliente no puede acceder a %s (redirige a acceso denegado)',
      (entry) => {
        logueadoComo(clientUser);
        renderApp(entry);

        expect(
          screen.getByRole('heading', { name: 'Acceso Denegado' })
        ).toBeInTheDocument();
        expect(
          screen.queryByText('Portal Administrador')
        ).not.toBeInTheDocument();
      }
    );

    it.each(rutasPanelAdmin)(
      'mecánico no puede acceder a %s (redirige a acceso denegado)',
      (entry) => {
        logueadoComo(mechanicUser);
        renderApp(entry);

        expect(
          screen.getByRole('heading', { name: 'Acceso Denegado' })
        ).toBeInTheDocument();
        expect(
          screen.queryByText('Portal Administrador')
        ).not.toBeInTheDocument();
      }
    );

    it.each(rutasPanelAdmin)(
      'administrador puede acceder a %s',
      (entry) => {
        logueadoComo(adminUser);
        renderApp(entry);

        expect(screen.getByText('Portal Administrador')).toBeInTheDocument();
        expect(
          screen.queryByRole('heading', { name: 'Acceso Denegado' })
        ).not.toBeInTheDocument();
        expect(
          screen.queryByRole('heading', { name: 'Iniciar Sesión' })
        ).not.toBeInTheDocument();
      }
    );

    it('muestra el mensaje del rol al negar acceso al panel a un cliente', () => {
      logueadoComo(clientUser);
      renderApp('/admin/inventario');

      expect(
        screen.getByRole('heading', { name: 'Acceso Denegado' })
      ).toBeInTheDocument();
      expect(
        screen.getByText(/Tu rol \(cliente\) no tiene permisos para acceder a esta sección\./)
      ).toBeInTheDocument();
    });

    it('desde acceso denegado el cliente vuelve a su propio panel', () => {
      logueadoComo(clientUser);
      renderApp('/admin');

      const irAPanel = screen.getByRole('button', { name: /Ir a mi Panel/i });
      fireEvent.click(irAPanel);

      expect(
        screen.getByRole('heading', { name: /Bienvenido/ })
      ).toBeInTheDocument();
    });

    it('con token pero sin usuario cargado no permite entrar al panel y redirige a login', async () => {
      const { authService } = await import('@/infrastructure/api/AuthService');
      vi.mocked(authService.getProfile).mockRejectedValue(new Error('Token inválido'));
      localStorage.setItem('token', 'token-sin-perfil');
      useAuthStore.setState({
        user: null,
        token: 'token-sin-perfil',
        isAuthenticated: false,
        isLoading: false,
        isInitializing: true,
      });
      renderApp('/admin');

      expect(
        await screen.findByRole('heading', { name: 'Iniciar Sesión' })
      ).toBeInTheDocument();
      expect(
        screen.queryByText('Portal Administrador')
      ).not.toBeInTheDocument();
      expect(
        screen.queryByRole('heading', { name: 'Acceso Denegado' })
      ).not.toBeInTheDocument();
    });
  });

  describe('portal cliente', () => {
    it('permite entrar a /client y ver mi portal', () => {
      logueadoComo(clientUser);
      renderApp('/client');

      expect(
        screen.getByRole('heading', { name: /Bienvenido/ })
      ).toBeInTheDocument();
      expect(screen.getAllByText('Mis Vehículos').length).toBeGreaterThan(0);
    });

    it('navega con un clic del menú hacia /client/vehiculos', async () => {
      logueadoComo(clientUser);
      renderApp('/client');

      fireEvent.click(screen.getByRole('link', { name: 'Mis Vehículos' }));

      expect(
        await screen.findByText(
          'Consulte la ficha técnica y el historial de sus vehículos registrados'
        )
      ).toBeInTheDocument();
    });

    it('niega /client a un administrador y lo lleva a acceso denegado', () => {
      logueadoComo(adminUser);
      renderApp('/client');

      expect(
        screen.getByRole('heading', { name: 'Acceso Denegado' })
      ).toBeInTheDocument();
      expect(screen.queryByText('Portal Cliente')).not.toBeInTheDocument();
    });

    it('niega /client a un mecánico y lo lleva a acceso denegado', () => {
      logueadoComo(mechanicUser);
      renderApp('/client');

      expect(
        screen.getByRole('heading', { name: 'Acceso Denegado' })
      ).toBeInTheDocument();
      expect(screen.queryByText('Portal Cliente')).not.toBeInTheDocument();
    });
  });

  describe('portal mecánico', () => {
    it('permite entrar a /mechanic y ver mi panel', () => {
      logueadoComo(mechanicUser);
      renderApp('/mechanic');

      expect(
        screen.getByRole('heading', { name: 'Panel del Mecánico' })
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

    it('niega /mechanic a un administrador y lo lleva a acceso denegado', () => {
      logueadoComo(adminUser);
      renderApp('/mechanic');

      expect(
        screen.getByRole('heading', { name: 'Acceso Denegado' })
      ).toBeInTheDocument();
      expect(screen.queryByText('Actualizar Estados')).not.toBeInTheDocument();
    });

    it('niega /mechanic a un cliente y lo lleva a acceso denegado', () => {
      logueadoComo(clientUser);
      renderApp('/mechanic');

      expect(
        screen.getByRole('heading', { name: 'Acceso Denegado' })
      ).toBeInTheDocument();
      expect(screen.queryByText('Actualizar Estados')).not.toBeInTheDocument();
    });
  });
});