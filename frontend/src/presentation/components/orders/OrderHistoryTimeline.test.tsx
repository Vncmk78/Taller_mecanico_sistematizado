import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import type { OrderHistoryEntry } from '@/domain/entities/OrderHistory';
import { formatDateTime } from '@/presentation/utils/orderDisplay';
import { OrderHistoryTimeline } from './OrderHistoryTimeline';

const entries: OrderHistoryEntry[] = [
    {
        id: 'h1',
        ordenId: '101',
        estadoAnteriorCodigo: 3,
        estadoNuevoCodigo: 5,
        actorUsuarioId: 1,
        origen: 'usuario',
        fecha: '2026-09-02T12:00:00',
        observacion: 'Trabajo autorizado',
        usuarioNombre: 'Martín Herrera',
    },
    {
        id: 'h2',
        ordenId: '101',
        estadoAnteriorCodigo: null,
        estadoNuevoCodigo: 1,
        actorUsuarioId: null,
        origen: 'sistema',
        fecha: '2026-09-01T10:15:00',
        observacion: 'Ingreso registrado por el administrador',
    },
];

describe('OrderHistoryTimeline: historial de estados de la orden', () => {
    it('muestra el skeleton mientras carga', () => {
        render(<OrderHistoryTimeline entries={[]} loading />);

        expect(screen.getByLabelText('Cargando historial')).toBeInTheDocument();
    });

    it('muestra el estado vacío cuando no hay historial', () => {
        render(<OrderHistoryTimeline entries={[]} loading={false} />);

        expect(
            screen.getByText('Aún no hay registros del historial de estados de esta orden.')
        ).toBeInTheDocument();
    });

    it('renderiza las entradas con estado, anterior, origen y observación', () => {
        render(<OrderHistoryTimeline entries={entries} loading={false} />);

        expect(screen.getByText('Historial de estados')).toBeInTheDocument();
        expect(screen.getByText('En reparación')).toBeInTheDocument();
        expect(
            screen.getByText('desde Esperando aprobación de presupuesto')
        ).toBeInTheDocument();
        expect(screen.getByText('Martín Herrera')).toBeInTheDocument();
        expect(screen.getByText(formatDateTime(entries[0].fecha))).toBeInTheDocument();
        expect(screen.getByText('Trabajo autorizado')).toBeInTheDocument();
        expect(screen.getAllByText('Sistema').length).toBeGreaterThan(0);
        expect(
            screen.getByText('Ingreso registrado por el administrador')
        ).toBeInTheDocument();
    });

    it('omite el estado anterior y la observación cuando no aplican', () => {
        const sinAntecesor: OrderHistoryEntry = {
            ...entries[0],
            estadoAnteriorCodigo: null,
            observacion: undefined,
        };

        render(<OrderHistoryTimeline entries={[sinAntecesor]} loading={false} />);

        expect(screen.queryByText(/desde /)).not.toBeInTheDocument();
        expect(screen.queryByText('Trabajo autorizado')).not.toBeInTheDocument();
        expect(screen.getByText('En reparación')).toBeInTheDocument();
    });
});