import { Routes, Route, Navigate } from 'react-router-dom';
import { LoginPage } from '@/presentation/pages/auth/LoginPage';
import { HomePage } from '@/presentation/pages/HomePage';
import { AccessDeniedPage } from '@/presentation/pages/errors/AccessDeniedPage';
import { AdminLayout } from '@/presentation/components/layout/AdminLayout';
import { AdminDashboardPage } from '@/presentation/pages/admin/AdminDashboardPage';
import { ProtectedRoute } from '@/presentation/components/auth/ProtectedRoute';

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/login" element={<LoginPage />} />
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
        <Route path="ordenes" element={<div className="p-10 text-text-muted">Órdenes - Próximamente</div>} />
        <Route path="clientes" element={<div className="p-10 text-text-muted">Clientes - Próximamente</div>} />
        <Route path="vehiculos" element={<div className="p-10 text-text-muted">Vehículos - Próximamente</div>} />
        <Route path="inventario" element={<div className="p-10 text-text-muted">Inventario - Próximamente</div>} />
        <Route path="distribuidores" element={<div className="p-10 text-text-muted">Distribuidores - Próximamente</div>} />
      </Route>

      <Route
        path="/client"
        element={
          <ProtectedRoute allowedRoles={['cliente']}>
            <div className="p-10 text-text-muted">Portal Cliente - Próximamente</div>
          </ProtectedRoute>
        }
      />
      <Route
        path="/mechanic"
        element={
          <ProtectedRoute allowedRoles={['mecanico']}>
            <div className="p-10 text-text-muted">Portal Mecánico - Próximamente</div>
          </ProtectedRoute>
        }
      />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}