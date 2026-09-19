import { Routes, Route, Navigate } from 'react-router-dom';
import { LoginPage } from '@/presentation/pages/auth/LoginPage';
import { HomePage } from '@/presentation/pages/HomePage';
import { AccessDeniedPage } from '@/presentation/pages/errors/AccessDeniedPage';
import { AdminLayout } from '@/presentation/components/layout/AdminLayout';
import { ClientLayout } from '@/presentation/components/layout/ClientLayout';
import { MechanicLayout } from '@/presentation/components/layout/MechanicLayout';
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
            <ClientLayout />
          </ProtectedRoute>
        }
      >
        <Route
          index
          element={
            <div className="p-10 text-text-muted animate-fade-in">
              <h2 className="text-3xl font-bold text-white mb-2 tracking-tight">Mi Portal</h2>
              <p>Bienvenido a tu espacio. Pronto podrás consultar el estado de tus servicios.</p>
            </div>
          }
        />
        <Route path="vehiculos" element={<div className="p-10 text-text-muted">Mis Vehículos - Próximamente</div>} />
        <Route path="servicios" element={<div className="p-10 text-text-muted">Estado del Servicio - Próximamente</div>} />
        <Route path="presupuestos" element={<div className="p-10 text-text-muted">Presupuestos - Próximamente</div>} />
      </Route>
      <Route
        path="/mechanic"
        element={
          <ProtectedRoute allowedRoles={['mecanico']}>
            <MechanicLayout />
          </ProtectedRoute>
        }
      >
        <Route
          index
          element={
            <div className="p-10 text-text-muted animate-fade-in">
              <h2 className="text-3xl font-bold text-white mb-2 tracking-tight">Mi Panel</h2>
              <p>Bienvenido. Aquí gestionarás tus órdenes asignadas y su estado.</p>
            </div>
          }
        />
        <Route path="ordenes" element={<div className="p-10 text-text-muted">Mis Órdenes - Próximamente</div>} />
        <Route path="estados" element={<div className="p-10 text-text-muted">Actualizar Estados - Próximamente</div>} />
        <Route path="historial" element={<div className="p-10 text-text-muted">Actividades - Próximamente</div>} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}