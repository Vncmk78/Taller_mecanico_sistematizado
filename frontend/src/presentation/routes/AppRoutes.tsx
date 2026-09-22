import { Routes, Route, Navigate } from 'react-router-dom';
import { LoginPage } from '@/presentation/pages/auth/LoginPage';
import { HomePage } from '@/presentation/pages/HomePage';
import { AccessDeniedPage } from '@/presentation/pages/errors/AccessDeniedPage';
import { AdminLayout } from '@/presentation/components/layout/AdminLayout';
import { ClientLayout } from '@/presentation/components/layout/ClientLayout';
import { MechanicLayout } from '@/presentation/components/layout/MechanicLayout';
import { AdminDashboardPage } from '@/presentation/pages/admin/AdminDashboardPage';
import { AdminVehiclesPage } from '@/presentation/pages/admin/AdminVehiclesPage';
import { AdminVehicleDetailPage } from '@/presentation/pages/admin/AdminVehicleDetailPage';
import { AdminOrdersPage } from '@/presentation/pages/admin/AdminOrdersPage';
import { AdminClientsPage } from '@/presentation/pages/admin/AdminClientsPage';
import { AdminInventoryPage } from '@/presentation/pages/admin/AdminInventoryPage';
import { AdminDistributorsPage } from '@/presentation/pages/admin/AdminDistributorsPage';
import { ClientDashboardPage } from '@/presentation/pages/client/ClientDashboardPage';
import { ClientVehiclesPage } from '@/presentation/pages/client/ClientVehiclesPage';
import { ClientVehicleFormPage } from '@/presentation/pages/client/ClientVehicleFormPage';
import { ClientVehicleDetailPage } from '@/presentation/pages/client/ClientVehicleDetailPage';
import { ClientServicesPage } from '@/presentation/pages/client/ClientServicesPage';
import { ClientBudgetsPage } from '@/presentation/pages/client/ClientBudgetsPage';
import { MechanicDashboardPage } from '@/presentation/pages/mechanic/MechanicDashboardPage';
import { MechanicVehiclesPage } from '@/presentation/pages/mechanic/MechanicVehiclesPage';
import { MechanicVehicleDetailPage } from '@/presentation/pages/mechanic/MechanicVehicleDetailPage';
import { MechanicOrdersPage } from '@/presentation/pages/mechanic/MechanicOrdersPage';
import { MechanicStatusPage } from '@/presentation/pages/mechanic/MechanicStatusPage';
import { MechanicHistoryPage } from '@/presentation/pages/mechanic/MechanicHistoryPage';
import { ProtectedRoute } from '@/presentation/components/auth/ProtectedRoute';
import { PublicOnlyRoute } from '@/presentation/components/auth/PublicOnlyRoute';

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route
        path="/login"
        element={
          <PublicOnlyRoute>
            <LoginPage />
          </PublicOnlyRoute>
        }
      />
      <Route path="/acceso-denegado" element={<AccessDeniedPage />} />

      <Route
        path="/admin"
        element={
          <ProtectedRoute allowedRoles={['administrador']}>
            <AdminLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<AdminDashboardPage />} />
        <Route path="ordenes" element={<AdminOrdersPage />} />
        <Route path="clientes" element={<AdminClientsPage />} />
        <Route path="vehiculos" element={<AdminVehiclesPage />} />
        <Route path="vehiculos/:id" element={<AdminVehicleDetailPage />} />
        <Route path="inventario" element={<AdminInventoryPage />} />
        <Route path="distribuidores" element={<AdminDistributorsPage />} />
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
        <Route path="servicios" element={<ClientServicesPage />} />
        <Route path="presupuestos" element={<ClientBudgetsPage />} />
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
        <Route path="ordenes" element={<MechanicOrdersPage />} />
        <Route path="estados" element={<MechanicStatusPage />} />
        <Route path="historial" element={<MechanicHistoryPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}