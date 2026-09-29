import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { RoleLayout, type RoleLayoutProps } from '@/presentation/components/layout/RoleLayout';

const seccionesAdmin = [
  {
    title: 'Portal Administrador',
    items: [
      { to: '/admin', label: 'Panel de Control', end: true },
      { to: '/admin/vehiculos', label: 'Vehículos' },
    ],
  },
];

const seccionesCliente = [
  {
    items: [
      { to: '/client', label: 'Mi Portal', end: true },
      { to: '/client/vehiculos', label: 'Mis Vehículos' },
    ],
  },
];

function renderRoleLayout(props: Partial<RoleLayoutProps> = {}, entry = '/admin') {
  const base: RoleLayoutProps = {
    variant: 'sidebar',
    sections: seccionesAdmin,
    userName: 'admin@taller.cl',
    userSubtitle: 'Administrador',
    onLogout: vi.fn(),
  };

  return render(
    <MemoryRouter initialEntries={[entry]}>
      <Routes>
        <Route element={<RoleLayout {...base} {...props} />}>
          <Route path="/admin" element={<div>Dashboard del portal</div>} />
          <Route path="/admin/vehiculos" element={<div>Catálogo de vehículos</div>} />
          <Route path="/client" element={<div>Portal del cliente</div>} />
          <Route path="/client/vehiculos" element={<div>Mis vehículos del cliente</div>} />
        </Route>
      </Routes>
    </MemoryRouter>
  );
}

describe('RoleLayout: layout y navegación reutilizable', () => {
  it('variante sidebar: muestra secciones, enlaces y datos del usuario', () => {
    renderRoleLayout();

    expect(screen.getByText('Portal Administrador')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Vehículos' })).toBeInTheDocument();
    expect(screen.getByText('admin@taller.cl')).toBeInTheDocument();
    expect(screen.getByText('Administrador')).toBeInTheDocument();
    expect(screen.getByText('Dashboard del portal')).toBeInTheDocument();
  });

  it('variante topnav: muestra badge, navegación superior y contenido', () => {
    renderRoleLayout({
      variant: 'topnav',
      sections: seccionesCliente,
      badge: 'Portal Cliente',
      userName: 'cliente@taller.cl',
      userSubtitle: 'Cliente',
    }, '/client');

    expect(screen.getByText('Portal Cliente')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Mis Vehículos' })).toBeInTheDocument();
    expect(screen.queryByText('Portal Administrador')).not.toBeInTheDocument();
    expect(screen.getByText('Portal del cliente')).toBeInTheDocument();
  });

  it('navega a la vista correspondiente con un clic en el enlace', async () => {
    renderRoleLayout();

    fireEvent.click(screen.getByRole('link', { name: 'Vehículos' }));

    expect(await screen.findByText('Catálogo de vehículos')).toBeInTheDocument();
    expect(screen.queryByText('Dashboard del portal')).not.toBeInTheDocument();
  });
});