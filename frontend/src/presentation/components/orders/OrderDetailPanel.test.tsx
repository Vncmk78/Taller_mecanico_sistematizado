import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import type { Order } from '@/domain/entities/Order';
import { formatDateTime } from '@/presentation/utils/orderDisplay';
import { OrderDetailPanel } from './OrderDetailPanel';

const order: Order = {
    id: '101',
    vehicleId: '1',
    ingresoId: 1,
    estadoCodigo: 5,
    mecanicoActualId: 'm1',
    creadoPorId: 'u1',
    creadoEn: '2026-09-01T10:15:00',
    actualizadoEn: '2026-09-05T16:30:00',
    patente: 'ABCD-12',
    vehiculo: 'Ford Fiesta',
    mecanicoNombre: 'Martín Herrera',
};

describe('OrderDetailPanel: panel de detalle de la orden', () => {
    it('muestra los datos de la orden y el estado', () => {
        render(<OrderDetailPanel order={order} patente={order.patente} vehicleLabel={order.vehiculo} />);

        expect(screen.getByText('Orden de trabajo n° 101')).toBeInTheDocument();
        expect(screen.getByText('En reparación')).toBeInTheDocument();
        expect(screen.getByText('ABCD-12')).toBeInTheDocument();
        expect(screen.getByText('Ford Fiesta')).toBeInTheDocument();
        expect(screen.getByText('Martín Herrera')).toBeInTheDocument();
        expect(screen.getByText('Ingreso (ficha n°)')).toBeInTheDocument();
        expect(screen.getByText('1')).toBeInTheDocument();
        expect(screen.getByText('Creada por (usuario)')).toBeInTheDocument();
        expect(screen.getByText('u1')).toBeInTheDocument();
        expect(screen.getByText(formatDateTime(order.creadoEn))).toBeInTheDocument();
        expect(screen.getByText(formatDateTime(order.actualizadoEn))).toBeInTheDocument();
    });

    it('usa el fallback del vehículo cuando no hay patente ni label', () => {
        render(<OrderDetailPanel order={{ ...order, patente: undefined, vehiculo: undefined }} />);

        expect(screen.getByText('Vehículo N°1')).toBeInTheDocument();
        expect(screen.queryByText('ABCD-12')).not.toBeInTheDocument();
    });

    it('usa los fallbacks del mecánico', () => {
        render(<OrderDetailPanel order={{ ...order, mecanicoNombre: undefined, mecanicoActualId: null }} />);

        expect(screen.getByText('Sin asignar')).toBeInTheDocument();

        render(<OrderDetailPanel order={{ ...order, mecanicoNombre: undefined }} />);

        expect(screen.getByText('Mecánico m1')).toBeInTheDocument();
    });

    it('no muestra el estado incorrecto del catálogo', () => {
        render(<OrderDetailPanel order={{ ...order, estadoCodigo: 8 }} />);

        expect(screen.getByText('Cancelado')).toBeInTheDocument();
        expect(screen.queryByText('En reparación')).not.toBeInTheDocument();
    });
});