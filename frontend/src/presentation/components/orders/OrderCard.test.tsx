import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { Order } from '@/domain/entities/Order';
import { formatDate } from '@/presentation/utils/orderDisplay';
import { OrderCard } from './OrderCard';

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

function renderCard(overrides: Partial<Parameters<typeof OrderCard>[0]> = {}) {
    return render(
        <MemoryRouter>
            <OrderCard
                order={order}
                detailPath="/admin/ordenes/101"
                patente={order.patente}
                vehicleLabel={order.vehiculo}
                mechanicName={order.mecanicoNombre}
                {...overrides}
            />
        </MemoryRouter>
    );
}

describe('OrderCard: tarjeta del listado de órdenes', () => {
    it('muestra número, patente, vehículo, estado y fecha de actualización', () => {
        renderCard();

        expect(screen.getByText('Orden n° 101')).toBeInTheDocument();
        expect(screen.getByText('ABCD-12')).toBeInTheDocument();
        expect(screen.getByText('Ford Fiesta')).toBeInTheDocument();
        expect(screen.getByText('En reparación')).toBeInTheDocument();
        expect(
            screen.getByText(`Actualizada el ${formatDate(order.actualizadoEn)}`)
        ).toBeInTheDocument();
    });

    it('muestra el mecánico cuando está disponible', () => {
        renderCard();

        expect(screen.getByText('Mecánico: Martín Herrera')).toBeInTheDocument();
    });

    it('omite el mecánico cuando no está disponible', () => {
        renderCard({ mechanicName: undefined });

        expect(screen.queryByText(/Mecánico:/)).not.toBeInTheDocument();
    });

    it('enlaza al detalle de la orden', () => {
        renderCard();

        expect(screen.getByRole('link', { name: 'Ver detalle' })).toHaveAttribute(
            'href',
            '/admin/ordenes/101'
        );
    });
});