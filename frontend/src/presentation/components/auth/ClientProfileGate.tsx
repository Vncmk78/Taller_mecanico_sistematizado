import { useEffect, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { UserCheck } from 'lucide-react';
import { useAuth } from '@/presentation/components/auth/authContext';
import { usePerfilClienteStore } from '@/infrastructure/stores/usePerfilClienteStore';
import { Alert } from '@/presentation/components/ui/Alert';
import { Button } from '@/presentation/components/ui/Button';
import { FullScreenLoader } from '@/presentation/components/ui/FullScreenLoader';
import { GlassCard } from '@/presentation/components/ui/GlassCard';

/**
 * Antes de mostrar el portal Cliente, asegura que exista el perfil Cliente de
 * MS2 (POST /api/clientes/perfil). Se ejecuta en cada inicio de sesión o
 * recarga: la operación es idempotente. Si falla, la cuenta ya existe y la
 * sesión sigue iniciada, así que se ofrece reintentar sin registrarse de nuevo.
 */
export function ClientProfileGate({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const estado = usePerfilClienteStore((s) => s.estado);
  const usuarioPreparado = usePerfilClienteStore((s) => s.usuarioPreparado);
  const error = usePerfilClienteStore((s) => s.error);
  const aviso = usePerfilClienteStore((s) => s.aviso);
  const preparar = usePerfilClienteStore((s) => s.preparar);
  const descartarAviso = usePerfilClienteStore((s) => s.descartarAviso);

  useEffect(() => {
    if (user) void preparar(user);
  }, [user, preparar]);

  if (!user) return <FullScreenLoader />;

  if (estado === 'error') {
    return (
      <main
        id="contenido-principal"
        className="min-h-screen flex items-center justify-center px-5 py-8 animate-fade-in"
      >
        <GlassCard className="w-full max-w-[520px] p-6 sm:p-10 text-center">
          <UserCheck aria-hidden className="w-12 h-12 mx-auto mb-4 text-primary-blue" />
          <h1 className="text-xl font-bold text-text-main mb-3">Tu cuenta ya está creada</h1>
          <p className="text-text-muted mb-4">
            Iniciaste sesión, pero no pudimos preparar tu perfil de cliente en el taller. No
            necesitas registrarte de nuevo: puedes reintentar ahora o más tarde, incluso después
            de volver a iniciar sesión.
          </p>
          {error && (
            <Alert tone="error" className="mb-6 justify-center">
              {error}
            </Alert>
          )}
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <Button variant="accent" onClick={() => void preparar(user)}>
              Reintentar
            </Button>
            <Button
              variant="secondary"
              onClick={() => {
                logout();
                navigate('/login', { replace: true });
              }}
            >
              Cerrar sesión
            </Button>
          </div>
        </GlassCard>
      </main>
    );
  }

  if (estado !== 'listo' || usuarioPreparado !== user.id) {
    return <FullScreenLoader message="Preparando tu perfil de cliente..." />;
  }

  return (
    <>
      {aviso && (
        <div className="px-4 pt-4">
          <Alert
            tone="warning"
            action={
              <button
                type="button"
                className="text-sm underline bg-transparent border-none cursor-pointer"
                onClick={descartarAviso}
              >
                Entendido
              </button>
            }
          >
            {aviso}
          </Alert>
        </div>
      )}
      {children}
    </>
  );
}
