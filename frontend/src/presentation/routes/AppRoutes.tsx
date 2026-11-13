import { Routes, Route, Navigate } from 'react-router-dom';
import { LoginPage } from '@/presentation/pages/auth/LoginPage';
import { RegisterPage } from '@/presentation/pages/auth/RegisterPage';
import { HomePage } from '@/presentation/pages/HomePage';
import { AccessDeniedPage } from '@/presentation/pages/errors/AccessDeniedPage';
import { AdminLayout } from '@/presentation/components/layout/AdminLayout';
import { ClientLayout } from '@/presentation/components/layout/ClientLayout';
import { MechanicLayout } from '@/presentation/components/layout/MechanicLayout';
import { AdminDashboardPage } from '@/presentation/pages/admin/AdminDashboardPage';
import { AdminVehiclesPage } from '@/presentation/pages/admin/AdminVehiclesPage';
import { AdminVehicleDetailPage } from '@/presentation/pages/admin/AdminVehicleDetailPage';
import { AdminOrdersPage } from '@/presentation/pages/admin/AdminOrdersPage';
import { AdminOrderDetailPage } from '@/presentation/pages/admin/AdminOrderDetailPage';
import { AdminClientsPage } from '@/presentation/pages/admin/AdminClientsPage';
import { AdminConfigurationPage } from '@/presentation/pages/admin/AdminConfigurationPage';
import { AdminInventoryPage } from '@/presentation/pages/admin/AdminInventoryPage';
import { AdminInventoryAlertsPage } from '@/presentation/pages/admin/AdminInventoryAlertsPage';
import { AdminInventoryMovementsPage } from '@/presentation/pages/admin/AdminInventoryMovementsPage';
import { AdminStockDetailPage } from '@/presentation/pages/admin/AdminStockDetailPage';
import { AdminThresholdPage } from '@/presentation/pages/admin/AdminThresholdPage';
import { AdminDistributorsPage } from '@/presentation/pages/admin/AdminDistributorsPage';
import { ClientDashboardPage } from '@/presentation/pages/client/ClientDashboardPage';
import { ClientVehiclesPage } from '@/presentation/pages/client/ClientVehiclesPage';
import { ClientVehicleFormPage } from '@/presentation/pages/client/ClientVehicleFormPage';
import { ClientVehicleDetailPage } from '@/presentation/pages/client/ClientVehicleDetailPage';
import { ClientVehicleEditPage } from '@/presentation/pages/client/ClientVehicleEditPage';
import { ClientServicesPage } from '@/presentation/pages/client/ClientServicesPage';
import { ClientBudgetsPage } from '@/presentation/pages/client/ClientBudgetsPage';
import { ClientBudgetDetailPage } from '@/presentation/pages/client/ClientBudgetDetailPage';
import { ClientOrdersPage } from '@/presentation/pages/client/ClientOrdersPage';
import { ClientOrderDetailPage } from '@/presentation/pages/client/ClientOrderDetailPage';
import { ClientOrderEvidencePage } from '@/presentation/pages/client/ClientOrderEvidencePage';
import { AdminNuevasAtencionesPage } from '@/presentation/pages/admin/AdminNuevasAtencionesPage';
import { AdminNuevaAtencionDetailPage } from '@/presentation/pages/admin/AdminNuevaAtencionDetailPage';
import { AdminCancelacionesPage } from '@/presentation/pages/admin/AdminCancelacionesPage';
import { AdminUsersPage } from '@/presentation/pages/admin/AdminUsersPage';
import { ClientNuevasAtencionesPage } from '@/presentation/pages/client/ClientNuevasAtencionesPage';
import { ClientNuevaAtencionDetailPage } from '@/presentation/pages/client/ClientNuevaAtencionDetailPage';
import { MechanicDashboardPage } from '@/presentation/pages/mechanic/MechanicDashboardPage';
import { MechanicVehiclesPage } from '@/presentation/pages/mechanic/MechanicVehiclesPage';
import { MechanicVehicleDetailPage } from '@/presentation/pages/mechanic/MechanicVehicleDetailPage';
import { MechanicOrdersPage } from '@/presentation/pages/mechanic/MechanicOrdersPage';
import { MechanicOrderDetailPage } from '@/presentation/pages/mechanic/MechanicOrderDetailPage';
import { BudgetEditor } from '@/presentation/components/budgets/BudgetEditor';
import { MechanicBudgetPage } from '@/presentation/pages/mechanic/MechanicBudgetPage';
import { MechanicStatusPage } from '@/presentation/pages/mechanic/MechanicStatusPage';
import { OrderEvidencePage } from '@/presentation/pages/shared/OrderEvidencePage';
import { NotificationsPage } from '@/presentation/pages/shared/NotificationsPage';
import { ProtectedRoute } from '@/presentation/components/auth/ProtectedRoute';
import { PublicOnlyRoute } from '@/presentation/components/auth/PublicOnlyRoute';
import { ClientProfileGate } from '@/presentation/components/auth/ClientProfileGate';

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
      <Route
        path="/registro"
        element={
          <PublicOnlyRoute>
            <RegisterPage />
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
        <Route path="ordenes/:id" element={<AdminOrderDetailPage />} />
        <Route path="ordenes/:id/presupuesto" element={<BudgetEditor administrador />} />
        <Route
          path="ordenes/:id/evidencias"
          element={<OrderEvidencePage backTo="/admin/ordenes" backLabel="Volver a la gestión de órdenes" canUpload />}
        />
        <Route path="nuevas-atenciones" element={<AdminNuevasAtencionesPage />} />
        <Route path="nuevas-atenciones/:id" element={<AdminNuevaAtencionDetailPage />} />
        <Route path="cancelaciones" element={<AdminCancelacionesPage />} />
        <Route path="usuarios" element={<AdminUsersPage />} />
        <Route path="clientes" element={<AdminClientsPage />} />
        <Route path="configuracion" element={<AdminConfigurationPage />} />
        <Route path="vehiculos" element={<AdminVehiclesPage />} />
        <Route path="vehiculos/:id" element={<AdminVehicleDetailPage />} />
        <Route path="inventario" element={<AdminInventoryPage />} />
        <Route path="inventario/alertas" element={<AdminInventoryAlertsPage />} />
        <Route path="inventario/movimientos" element={<AdminInventoryMovementsPage />} />
        <Route path="inventario/stock/:repuestoId" element={<AdminStockDetailPage />} />
        <Route path="inventario/umbral" element={<AdminThresholdPage />} />
        <Route path="distribuidores" element={<AdminDistributorsPage />} />
        <Route path="notificaciones" element={<NotificationsPage />} />
      </Route>

      <Route
        path="/client"
        element={
          <ProtectedRoute allowedRoles={['cliente']}>
            {/* El portal Cliente usa vehículos y órdenes de MS2: exige su perfil. */}
            <ClientProfileGate>
              <ClientLayout />
            </ClientProfileGate>
          </ProtectedRoute>
        }
      >
        <Route index element={<ClientDashboardPage />} />
        <Route path="vehiculos" element={<ClientVehiclesPage />} />
        <Route path="vehiculos/nuevo" element={<ClientVehicleFormPage />} />
        <Route path="vehiculos/:id" element={<ClientVehicleDetailPage />} />
        <Route path="vehiculos/:id/editar" element={<ClientVehicleEditPage />} />
        <Route path="agendar" element={<Navigate to="/client/ordenes" replace />} />
        <Route path="servicios" element={<ClientServicesPage />} />
        <Route path="ordenes" element={<ClientOrdersPage />} />
        <Route path="ordenes/:id" element={<ClientOrderDetailPage />} />
        <Route path="ordenes/:id/evidencias" element={<ClientOrderEvidencePage />} />
        <Route path="nuevas-atenciones" element={<ClientNuevasAtencionesPage />} />
        <Route path="nuevas-atenciones/:id" element={<ClientNuevaAtencionDetailPage />} />
        <Route path="presupuestos" element={<ClientBudgetsPage />} />
        <Route path="presupuestos/:ordenId" element={<ClientBudgetDetailPage />} />
        <Route path="notificaciones" element={<NotificationsPage />} />
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
        <Route path="ordenes/:id" element={<MechanicOrderDetailPage />} />
        <Route path="ordenes/:id/presupuesto" element={<MechanicBudgetPage />} />
        <Route
          path="ordenes/:id/evidencias"
          element={<OrderEvidencePage backTo="/mechanic/ordenes" backLabel="Volver a mis órdenes" canUpload />}
        />
        <Route path="estados" element={<MechanicStatusPage />} />
        <Route path="notificaciones" element={<NotificationsPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}