import { beforeEach, describe, expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useNavigate } from 'react-router-dom';
import { RouteChangeFocus } from '@/presentation/components/layout/RouteChangeFocus';

function Harness() {
  const navigate = useNavigate();
  return (
    <>
      <RouteChangeFocus />
      <main id="contenido-principal" tabIndex={-1}>
        Contenido principal
      </main>
      <button type="button" onClick={() => navigate('/otra')}>
        Ir a otra
      </button>
    </>
  );
}

function renderHarness(entry: string) {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <Routes>
        <Route path="/inicio" element={<Harness />} />
        <Route path="/otra" element={<Harness />} />
      </Routes>
    </MemoryRouter>
  );
}

describe('RouteChangeFocus: gestión de foco al cambiar de ruta', () => {
  beforeEach(() => {
    (document.activeElement as HTMLElement | null)?.blur();
  });

  it('no roba el foco en el montaje inicial', () => {
    renderHarness('/inicio');

    expect(document.activeElement).not.toBe(document.getElementById('contenido-principal'));
  });

  it('mueve el foco al contenido principal al navegar', () => {
    renderHarness('/inicio');

    fireEvent.click(screen.getByRole('button', { name: 'Ir a otra' }));

    expect(document.activeElement).toBe(document.getElementById('contenido-principal'));
  });
});