import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { mockEvidenciaFrenos, mockEvidenciasOrden101 } from '@/infrastructure/mocks/evidence.mock';
import { EvidenceContextFilter } from './EvidenceContextFilter';

describe('EvidenceContextFilter: chips por contexto', () => {
    it('muestra un chip por contexto presente con su conteo y "Todos" con el total', () => {
        render(
            <EvidenceContextFilter
                evidencias={mockEvidenciasOrden101}
                contexto="todos"
                onChange={() => {}}
            />
        );

        expect(screen.getByRole('group', { name: 'Filtrar evidencia por contexto' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Todos (3)' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Diagnóstico (1)' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Resultado final (2)' })).toBeInTheDocument();
        // No hay evidencias de esos contextos: no se ofrecen.
        expect(screen.queryByRole('button', { name: /Presupuesto \(/ })).not.toBeInTheDocument();
        expect(screen.queryByRole('button', { name: /Reparación \(/ })).not.toBeInTheDocument();
    });

    it('marca con aria-pressed la selección vigente y avisa el cambio', () => {
        const onChange = vi.fn();
        render(
            <EvidenceContextFilter
                evidencias={mockEvidenciasOrden101}
                contexto="resultado_final"
                onChange={onChange}
            />
        );

        expect(screen.getByRole('button', { name: 'Todos (3)' })).toHaveAttribute('aria-pressed', 'false');
        expect(screen.getByRole('button', { name: 'Resultado final (2)' })).toHaveAttribute(
            'aria-pressed',
            'true'
        );

        fireEvent.click(screen.getByRole('button', { name: 'Diagnóstico (1)' }));
        expect(onChange).toHaveBeenCalledWith('diagnostico');
        fireEvent.click(screen.getByRole('button', { name: 'Todos (3)' }));
        expect(onChange).toHaveBeenCalledWith('todos');
    });

    it('no se renderiza cuando la lista cubre un solo contexto', () => {
        const { container } = render(
            <EvidenceContextFilter evidencias={[mockEvidenciaFrenos]} contexto="todos" onChange={() => {}} />
        );
        expect(container).toBeEmptyDOMElement();
    });

    it('no se renderiza sin evidencias', () => {
        const { container } = render(
            <EvidenceContextFilter evidencias={[]} contexto="todos" onChange={() => {}} />
        );
        expect(container).toBeEmptyDOMElement();
    });
});
