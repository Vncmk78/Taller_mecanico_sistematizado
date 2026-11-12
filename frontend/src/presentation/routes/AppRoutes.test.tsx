import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { User } from '@/domain/entities/User';
import { authService } from '@/infrastructure/api/AuthService';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { usePerfilClienteStore } from '@/infrastructure/stores/usePerfilClienteStore';
import { perfilClienteService } from '@/infrastructure/api/PerfilClienteService';
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

vi.mock('@/infrastructure/api/PerfilClienteService', () => ({
  perfilClienteService: {
    preparar: vi.fn(() =>
      Promise.resolve({ perfil: { clienteId: '7', usuarioId: '2', telefono: null }, creado: false })
    ),
  },
}));

vi.mock('@/infrastructure/api/NuevaAtencionService', () => ({
  nuevaAtencionService: {
    listar: vi.fn(() => Promise.resolve({ items: [], total: 0, limit: 20, offset: 0 })),
    obtener: vi.fn(),
    solicitar: vi.fn(),
    revisar: vi.fn(),
    generarOrden: vi.fn(),
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
  vi.mocked(perfilClienteService.preparar).mockClear();
  useAuthStore.setState({
    user: null,
    token: null,
    isAuthenticated: false,
    isLoading: false,
    isInitializing: false,
  });
  // Por defecto el perfil Cliente de MS2 ya está preparado en esta sesión; las
  // pruebas del control de preparación lo reinician explícitamente.
  usePerfilClienteStore.getState().reset();
  usePerfilClienteStore.setState({ estado: 'listo', usuarioPreparado: clientUser.id });
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

    it('/registro muestra el formulario público de registro', () => {
      renderApp('/registro');

      expect(
        screen.getByRole('heading', { name: 'Crear cuenta de cliente' })
      ).toBeInTheDocument();
      expect(screen.queryByLabelText(/rol/i)).not.toBeInTheDocument();
    });

    it('el login y el home enlazan al registro', () => {
      renderApp('/login');
      expect(screen.getByRole('link', { name: 'Crear cuenta de cliente' })).toHaveAttribute(
        'href',
        '/registro'
      );
    });

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

    it('navega desde el menú a las solicitudes de nueva atención', async () => {
      logueadoComo(adminUser);
      renderApp('/admin');

      fireEvent.click(screen.getByRole('link', { name: 'Nuevas atenciones' }));

      expect(
        await screen.findByRole('heading', { name: 'Solicitudes de nueva atención' })
      ).toBeInTheDocument();
    });

    it('una cuenta multirrol con Administrador entra sin preparar el perfil Cliente', async () => {
      usePerfilClienteStore.getState().reset();
      logueadoComo({ ...clientUser, role: 'cliente', roles: ['cliente', 'administrador'] });
      renderApp('/admin/nuevas-atenciones');

      expect(
        await screen.findByRole('heading', { name: 'Solicitudes de nueva atención' })
      ).toBeInTheDocument();
      expect(perfilClienteService.preparar).not.toHaveBeenCalled();
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

    it('prepara el perfil Cliente de MS2 antes de mostrar el portal', async () => {
      usePerfilClienteStore.getState().reset();
      logueadoComo(clientUser);
      renderApp('/client');

      expect(
        await screen.findByRole('heading', { name: /Bienvenido/ })
      ).toBeInTheDocument();
      expect(perfilClienteService.preparar).toHaveBeenCalledTimes(1);
    });

    it('un cliente con sesión que abre /registro vuelve a su portal', () => {
      logueadoComo(clientUser);
      renderApp('/registro');

      expect(
        screen.getByRole('heading', { name: /Bienvenido/ })
      ).toBeInTheDocument();
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

  describe('recarga o enlace directo con sesión guardada', () => {
    // Estado real tras recargar el navegador: hay token, pero el usuario aún
    // no se recuperó de GET /auth/me (useAuthStore arranca inicializando).
    function recargaConToken() {
      localStorage.setItem('token', 'token-guardado');
      useAuthStore.setState({
        user: null,
        token: 'token-guardado',
        isAuthenticated: true,
        isLoading: false,
        isInitializing: true,
      });
    }

    it('conserva la subruta del administrador al restaurar la sesión', async () => {
      vi.mocked(authService.getProfile).mockResolvedValueOnce(adminUser);
      recargaConToken();
      renderApp('/admin/configuracion');

      expect(
        await screen.findByRole('heading', { name: 'Capacidad del taller' })
      ).toBeInTheDocument();
      expect(screen.queryByRole('heading', { name: 'Iniciar Sesión' })).not.toBeInTheDocument();
    });

    it('conserva la subruta del cliente y prepara su perfil antes de mostrarla', async () => {
      usePerfilClienteStore.getState().reset();
      vi.mocked(authService.getProfile).mockResolvedValueOnce(clientUser);
      recargaConToken();
      renderApp('/client/vehiculos');

      expect(
        await screen.findByText('Consulte la ficha técnica y el historial de sus vehículos registrados')
      ).toBeInTheDocument();
      expect(perfilClienteService.preparar).toHaveBeenCalledTimes(1);
    });

    it('mientras restaura no muestra el login ni el portal', () => {
      recargaConToken(); // getProfile queda pendiente (mock por defecto)
      renderApp('/admin/ordenes');

      expect(screen.queryByRole('heading', { name: 'Iniciar Sesión' })).not.toBeInTheDocument();
      expect(screen.queryByRole('heading', { name: 'Gestión de Órdenes' })).not.toBeInTheDocument();
      expect(screen.getByText('Verificando sesión...')).toBeInTheDocument();
    });

    it('con token vencido pide iniciar sesión y luego vuelve al enlace pedido', async () => {
      vi.mocked(authService.getProfile).mockRejectedValueOnce(new Error('Token vencido'));
      vi.mocked(authService.login).mockResolvedValueOnce({
        access_token: 'token-nuevo', token_type: 'bearer', user: adminUser,
      });
      recargaConToken();
      renderApp('/admin/configuracion');

      expect(await screen.findByRole('heading', { name: 'Iniciar Sesión' })).toBeInTheDocument();
      expect(localStorage.getItem('token')).toBeNull();

      fireEvent.change(screen.getByLabelText('Correo Electrónico'), { target: { value: 'admin@taller.cl' } });
      fireEvent.change(screen.getByLabelText('Contraseña'), { target: { value: 'AdminPrueba123!' } });
      fireEvent.click(screen.getByRole('button', { name: 'Ingresar a mi cuenta' }));

      expect(
        await screen.findByRole('heading', { name: 'Capacidad del taller' })
      ).toBeInTheDocument();
    });

    it('un enlace de otro portal lleva a acceso denegado, no al login', async () => {
      vi.mocked(authService.getProfile).mockResolvedValueOnce(clientUser);
      recargaConToken();
      renderApp('/admin/ordenes');

      expect(await screen.findByRole('heading', { name: 'Acceso Denegado' })).toBeInTheDocument();
    });
  });
});
