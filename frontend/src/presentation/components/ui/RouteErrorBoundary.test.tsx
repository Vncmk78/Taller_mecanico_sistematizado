import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { Link, MemoryRouter, Route, Routes } from 'react-router-dom';
import { RouteErrorBoundary } from '@/presentation/components/ui/RouteErrorBoundary';

function RutaQueExplota(): never {
    throw new Error('boom');
}

describe('RouteErrorBoundary: recuperación de errores de render por navegación', () => {
    it('muestra el fallback y renderiza la otra ruta al navegar, sin recargar', () => {
        const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
        render(
            <MemoryRouter initialEntries={['/rota']}>
                <RouteErrorBoundary fallback={<Link to="/">Volver al inicio</Link>}>
                    <Routes>
                        <Route path="/" element={<p>Página sana</p>} />
                        <Route path="/rota" element={<RutaQueExplota />} />
                    </Routes>
                </RouteErrorBoundary>
            </MemoryRouter>
        );

        // La página rota muestra el fallback mientras el error está activo.
        expect(screen.getByRole('link', { name: 'Volver al inicio' })).toBeInTheDocument();
        expect(screen.queryByText('Página sana')).not.toBeInTheDocument();

        // Al navegar cambia el pathname (resetKey) y el boundary descarta el
        // error: la app sigue viva en vez de quedar inutilizable hasta recargar.
        fireEvent.click(screen.getByRole('link', { name: 'Volver al inicio' }));

        expect(screen.getByText('Página sana')).toBeInTheDocument();
        expect(screen.queryByRole('link', { name: 'Volver al inicio' })).not.toBeInTheDocument();
        consoleSpy.mockRestore();
    });

    it('no interfiere con rutas que renderizan sin errores', () => {
        render(
            <MemoryRouter initialEntries={['/sana']}>
                <RouteErrorBoundary>
                    <Routes>
                        <Route path="/sana" element={<p>Página sana</p>} />
                    </Routes>
                </RouteErrorBoundary>
            </MemoryRouter>
        );

        expect(screen.getByText('Página sana')).toBeInTheDocument();
    });

    it('usa el fallback por defecto del ErrorBoundary si no se entrega uno', () => {
        const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
        render(
            <MemoryRouter initialEntries={['/rota']}>
                <RouteErrorBoundary>
                    <Routes>
                        <Route path="/" element={<p>Página sana</p>} />
                        <Route path="/rota" element={<RutaQueExplota />} />
                    </Routes>
                </RouteErrorBoundary>
            </MemoryRouter>
        );

        expect(screen.getByRole('heading', { name: 'Algo salió mal' })).toBeInTheDocument();
        consoleSpy.mockRestore();
    });
});
