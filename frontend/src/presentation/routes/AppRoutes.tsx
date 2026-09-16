import { Routes, Route, Navigate } from 'react-router-dom';
import { LoginPage } from '@/presentation/pages/auth/LoginPage';
import { HomePage } from '@/presentation/pages/HomePage';
import { AdminLayout } from '@/presentation/components/layout/AdminLayout';
import { AdminDashboardPage } from '@/presentation/pages/admin/AdminDashboardPage';
import { AdminVehiclesPage } from '@/presentation/pages/admin/AdminVehiclesPage';
import { AdminVehicleDetailPage } from '@/presentation/pages/admin/AdminVehicleDetailPage';
import { ClientLayout } from '@/presentation/components/layout/ClientLayout';
import { ClientDashboardPage } from '@/presentation/pages/client/ClientDashboardPage';
import { ClientVehiclesPage } from '@/presentation/pages/client/ClientVehiclesPage';
import { ClientVehicleFormPage } from '@/presentation/pages/client/ClientVehicleFormPage';
import { ClientVehicleDetailPage } from '@/presentation/pages/client/ClientVehicleDetailPage';
import { MechanicLayout } from '@/presentation/components/layout/MechanicLayout';
import { MechanicDashboardPage } from '@/presentation/pages/mechanic/MechanicDashboardPage';
import { MechanicVehiclesPage } from '@/presentation/pages/mechanic/MechanicVehiclesPage';
import { MechanicVehicleDetailPage } from '@/presentation/pages/mechanic/MechanicVehicleDetailPage';
import { ProtectedRoute } from '@/presentation/components/auth/ProtectedRoute';

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/login" element={<LoginPage />} />

      <Route
        path="/admin"
        element={
          <ProtectedRoute allowedRoles={['administrador']}>
            <AdminLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<AdminDashboardPage />} />
        <Route path="ordenes" element={<div className="p-10 text-text-muted">Órdenes - Próximamente</div>} />
        <Route path="clientes" element={<div className="p-10 text-text-muted">Clientes - Próximamente</div>} />
        <Route path="vehiculos" element={<AdminVehiclesPage />} />
        <Route path="vehiculos/:id" element={<AdminVehicleDetailPage />} />
        <Route path="inventario" element={<div className="p-10 text-text-muted">Inventario - Próximamente</div>} />
        <Route path="distribuidores" element={<div className="p-10 text-text-muted">Distribuidores - Próximamente</div>} />
      </Route>

      <Route
        path="/client"
        element={
          <ProtectedRoute allowedRoles={['cliente']}>
            <ClientLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<ClientDashboardPage />} />
        <Route path="vehiculos" element={<ClientVehiclesPage />} />
        <Route path="vehiculos/nuevo" element={<ClientVehicleFormPage />} />
        <Route path="vehiculos/:id" element={<ClientVehicleDetailPage />} />
        <Route path="agendar" element={<div className="text-text-muted">Agendar Mantención - Próximamente</div>} />
      </Route>

      <Route
        path="/mechanic"
        element={
          <ProtectedRoute allowedRoles={['mecanico']}>
            <MechanicLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<MechanicDashboardPage />} />
        <Route path="vehiculos" element={<MechanicVehiclesPage />} />
        <Route path="vehiculos/:id" element={<MechanicVehicleDetailPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}