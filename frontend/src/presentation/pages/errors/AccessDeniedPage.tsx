import { Link, useLocation, useNavigate } from 'react-router-dom';
import { ShieldAlert, Settings, Wrench, LogOut, LayoutDashboard } from 'lucide-react';
import { Button } from '@/presentation/components/ui/Button';
import { GlassCard } from '@/presentation/components/ui/GlassCard';
import { useAuth } from '@/presentation/components/auth/authContext';
import { getHomePath } from '@/presentation/routes/rolePaths';

interface AccessDeniedState {
  message?: string;
}

export function AccessDeniedPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();

  const message = (location.state as AccessDeniedState | null)?.message;

  const handleLogout = () => {
    logout();
    navigate('/login', { replace: true });
  };

  return (
    <div className="min-h-screen flex flex-col animate-fade-in">
      <nav className="flex justify-between items-center px-12 py-5 border-b border-border-custom bg-black/80 backdrop-blur-[10px] sticky top-0 z-50">
        <Link to="/" className="flex items-center gap-2.5 text-2xl font-bold no-underline text-white">
          <span className="relative inline-block w-[35px] h-[35px] text-gray-400">
            <Settings className="absolute left-0 top-0 w-6 h-6" />
            <Wrench className="absolute left-3 top-3 w-4 h-4 text-primary-red -rotate-15" />
          </span>
          Sistema Mecánico
        </Link>
        <Link
          to="/"
          className="bg-white/5 border border-border-custom text-white px-6 py-3 rounded-lg transition-all duration-300 hover:bg-white/15 hover:border-white/30 no-underline flex items-center gap-2"
        >
          Volver al Inicio
        </Link>
      </nav>

      <div className="flex flex-col items-center justify-center flex-grow px-5 py-8">
        <GlassCard className="w-full max-w-[480px] p-[50px_40px] text-center">
          <ShieldAlert className="w-20 h-20 mx-auto mb-5 text-status-red" />
          <h1 className="text-3xl font-bold tracking-tight text-white">
            Acceso Denegado
          </h1>
          <p className="mt-2 text-status-red text-sm font-bold tracking-wide uppercase">
            Error 403
          </p>
          <p className="mt-3 text-text-muted text-base">
            No tienes permisos para realizar esta acción. Si crees que es un error,
            contacta al administrador del sistema.
          </p>

          {message && (
            <div className="flex items-center justify-center gap-2 mt-4 text-status-orange text-sm bg-status-orange/10 border border-status-orange/40 rounded-lg px-4 py-3">
              {message}
            </div>
          )}

          <div className="flex flex-col gap-3 mt-8">
            <Link to={getHomePath(user?.role)} className="no-underline">
              <Button variant="primary" className="w-full py-4 text-lg">
                <LayoutDashboard className="w-5 h-5" />
                Ir a mi Panel
              </Button>
            </Link>
            <Button variant="secondary" onClick={handleLogout} className="w-full py-3">
              <LogOut className="w-5 h-5" />
              Cerrar Sesión
            </Button>
          </div>
        </GlassCard>
      </div>
    </div>
  );
}