import { beforeEach, describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { User } from '@/domain/entities/User';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { ClientDashboardPage } from './ClientDashboardPage';

// Cliente autenticado: identidad real de la sesión.
const cliente: User = {
    id: 'c1',
    email: 'cliente@taller.cl',
    full_name: 'Cliente Test',
    role: 'cliente',
    is_active: true,
};

function renderPage() {
    return render(
        <MemoryRouter>
            <ClientDashboardPage />
        </MemoryRouter>
    );
}

describe('ClientDashboardPage: resumen del portal según el cliente autenticado', () => {
    beforeEach(() => {
        useAuthStore.setState({ user: null, token: null, isAuthenticated: false, isLoading: false, isInitializing: false });
    });

    it('saluda con el nombre completo del cliente autenticado', () => {
        useAuthStore.setState({ user: cliente, token: 'token', isAuthenticated: true, isLoading: false, isInitializing: false });

        renderPage();

        expect(
            screen.getByRole('heading', { name: 'Bienvenido, Cliente Test' })
        ).toBeInTheDocument();
    });

    it('sin sesión autenticada muestra el saludo genérico', () => {
        renderPage();

        expect(screen.getByRole('heading', { name: 'Bienvenido' })).toBeInTheDocument();
    });

    it('enlaza a mis vehículos y a agendar mantención desde la sesión actual', () => {
        useAuthStore.setState({ user: cliente, token: 'token', isAuthenticated: true, isLoading: false, isInitializing: false });

        renderPage();

        expect(
            screen.getByRole('link', { name: /Mis Vehículos/ })
        ).toHaveAttribute('href', '/client/vehiculos');
        expect(
            screen.getByRole('link', { name: /Agendar Mantención/ })
        ).toHaveAttribute('href', '/client/agendar');
    });
});