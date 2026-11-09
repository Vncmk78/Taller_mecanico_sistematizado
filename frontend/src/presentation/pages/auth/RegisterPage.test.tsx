import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AxiosError, AxiosHeaders, type InternalAxiosRequestConfig } from 'axios';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type { User } from '@/domain/entities/User';
import { authService } from '@/infrastructure/api/AuthService';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { usePerfilClienteStore } from '@/infrastructure/stores/usePerfilClienteStore';
import { AuthProvider } from '@/presentation/components/auth/AuthProvider';
import { LoginPage } from '@/presentation/pages/auth/LoginPage';
import { RegisterPage } from '@/presentation/pages/auth/RegisterPage';

vi.mock('@/infrastructure/api/AuthService', () => ({
  authService: {
    register: vi.fn(),
    login: vi.fn(),
    getProfile: vi.fn(() => new Promise<never>(() => {})),
  },
}));

const creado: User = {
  id: '42',
  email: 'ana@correo.cl',
  full_name: 'Ana Pérez',
  role: 'cliente',
  roles: ['cliente'],
  is_active: true,
};

function errorHttp(status: number, data: unknown): AxiosError {
  const config = { headers: new AxiosHeaders() } as InternalAxiosRequestConfig;
  return new AxiosError('fallo', String(status), config, undefined, {
    status,
    statusText: '',
    headers: {},
    config,
    data,
  });
}

beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
  useAuthStore.setState({
    user: null,
    token: null,
    isAuthenticated: false,
    isLoading: false,
    isInitializing: false,
  });
  usePerfilClienteStore.getState().reset();
});

function renderRegistro() {
  return render(
    <MemoryRouter initialEntries={['/registro']}>
      <AuthProvider>
        <Routes>
          <Route path="/registro" element={<RegisterPage />} />
          <Route path="/login" element={<LoginPage />} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>
  );
}

function completar(datos: Partial<Record<string, string>> = {}) {
  const valores = {
    'Nombre completo': 'Ana Pérez',
    'Correo Electrónico': 'ana@correo.cl',
    Contraseña: 'clave-segura-123',
    'Confirmar contraseña': 'clave-segura-123',
    ...datos,
  };
  for (const [etiqueta, valor] of Object.entries(valores)) {
    fireEvent.change(screen.getByLabelText(etiqueta), { target: { value: valor } });
  }
}

const enviar = () => fireEvent.click(screen.getByRole('button', { name: 'Crear mi cuenta' }));

describe('RegisterPage: registro público de clientes', () => {
  it('no ofrece elegir rol: solo nombre, correo, contraseña y teléfono opcional', () => {
    renderRegistro();

    expect(screen.queryByLabelText(/rol/i)).not.toBeInTheDocument();
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
    expect(screen.getByLabelText('Teléfono de contacto (opcional)')).toBeInTheDocument();
  });

  it('crea la cuenta enviando solo los campos del contrato y lleva al login con confirmación', async () => {
    vi.mocked(authService.register).mockResolvedValue(creado);
    renderRegistro();

    completar({ 'Teléfono de contacto (opcional)': ' +56 9 1234 5678 ' });
    enviar();

    expect(
      await screen.findByText('Cuenta de cliente creada. Inicia sesión para continuar.')
    ).toBeInTheDocument();
    expect(authService.register).toHaveBeenCalledTimes(1);
    expect(authService.register).toHaveBeenCalledWith({
      full_name: 'Ana Pérez',
      email: 'ana@correo.cl',
      password: 'clave-segura-123',
    });
    expect(screen.getByLabelText('Correo Electrónico')).toHaveValue('ana@correo.cl');
    // El teléfono queda pendiente para preparar el perfil de MS2 tras el login.
    expect(usePerfilClienteStore.getState().telefonoPendiente).toEqual({
      email: 'ana@correo.cl',
      telefono: '+56 9 1234 5678',
    });
  });

  it('valida los campos antes de llamar a la API', async () => {
    renderRegistro();

    completar({
      'Nombre completo': 'A',
      'Correo Electrónico': 'no-es-correo',
      Contraseña: 'corta',
      'Confirmar contraseña': 'otra',
    });
    enviar();

    expect(
      await screen.findByText('El nombre debe tener al menos 2 caracteres')
    ).toBeInTheDocument();
    expect(screen.getByText('Ingrese un correo válido')).toBeInTheDocument();
    expect(
      screen.getByText('La contraseña debe tener al menos 8 caracteres')
    ).toBeInTheDocument();
    expect(screen.getByText('Las contraseñas no coinciden')).toBeInTheDocument();
    expect(authService.register).not.toHaveBeenCalled();
  });

  it('una contraseña de 8 caracteres solo por espacios exteriores se rechaza como en MS1', async () => {
    renderRegistro();

    completar({ Contraseña: '  abc12  ', 'Confirmar contraseña': '  abc12  ' });
    enviar();

    expect(
      await screen.findByText('La contraseña debe tener al menos 8 caracteres')
    ).toBeInTheDocument();
    expect(authService.register).not.toHaveBeenCalled();
  });

  it('muestra el correo duplicado (409) junto al campo de correo', async () => {
    vi.mocked(authService.register).mockRejectedValue(
      errorHttp(409, { detail: 'El correo ya está registrado' })
    );
    renderRegistro();

    completar();
    enviar();

    expect(
      await screen.findByText('Este correo ya está registrado. Inicia sesión o usa otro correo.')
    ).toBeInTheDocument();
    expect(screen.getByLabelText('Correo Electrónico')).toHaveAttribute('aria-invalid', 'true');
  });

  it('traslada los 422 de MS1 al campo correspondiente', async () => {
    vi.mocked(authService.register).mockRejectedValue(
      errorHttp(422, {
        detail: [
          {
            type: 'value_error',
            loc: ['body', 'email'],
            msg: 'value is not a valid email address',
            input: 'x',
          },
        ],
      })
    );
    renderRegistro();

    completar();
    enviar();

    expect(await screen.findByText('Ingrese un correo válido')).toBeInTheDocument();
  });

  it('muestra el fallo del servidor como mensaje general', async () => {
    vi.mocked(authService.register).mockRejectedValue(
      errorHttp(500, { detail: 'No fue posible registrar el usuario' })
    );
    renderRegistro();

    completar();
    enviar();

    expect(await screen.findByText('No fue posible registrar el usuario')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Crear mi cuenta' })).toBeEnabled();
  });

  it('sin conexión sugiere iniciar sesión por si la cuenta ya se creó', async () => {
    vi.mocked(authService.register).mockRejectedValue(errorHttp(504, {}));
    renderRegistro();

    completar();
    enviar();

    expect(
      await screen.findByText(/es posible que la cuenta se haya creado/)
    ).toBeInTheDocument();
  });

  it('ignora envíos repetidos mientras la creación está en curso', async () => {
    let resolver: (u: User) => void = () => {};
    vi.mocked(authService.register).mockImplementation(
      () => new Promise<User>((r) => (resolver = r))
    );
    renderRegistro();
    completar();

    const formulario = screen.getByRole('form', { name: 'Registro de cliente' });
    const boton = screen.getByRole('button', { name: 'Crear mi cuenta' });
    // Dos envíos en el mismo instante (doble Enter) y, ya en curso, más intentos.
    fireEvent.submit(formulario);
    fireEvent.submit(formulario);
    await waitFor(() => expect(authService.register).toHaveBeenCalledTimes(1));
    fireEvent.submit(formulario);
    fireEvent.click(boton);

    expect(boton).toBeDisabled();
    resolver(creado);
    expect(
      await screen.findByText('Cuenta de cliente creada. Inicia sesión para continuar.')
    ).toBeInTheDocument();
    expect(authService.register).toHaveBeenCalledTimes(1);
  });
});
