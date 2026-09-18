import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import axios from 'axios';
import { Mail, Lock, Eye, EyeOff, Settings, Wrench, AlertCircle } from 'lucide-react';
import { Button } from '@/presentation/components/ui/Button';
import { Input } from '@/presentation/components/ui/Input';
import { GlassCard } from '@/presentation/components/ui/GlassCard';
import { useAuth } from '@/presentation/components/auth/authContext';
import { getHomePath } from '@/presentation/routes/rolePaths';

const loginSchema = z.object({
  email: z.string().email('Ingrese un correo válido'),
  password: z.string().min(6, 'La contraseña debe tener al menos 6 caracteres'),
});

type LoginForm = z.infer<typeof loginSchema>;

export function LoginPage() {
  const [showPassword, setShowPassword] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const navigate = useNavigate();
  const location = useLocation();
  const { login, isLoading } = useAuth();

  const from = (location.state as { from?: string } | null)?.from;

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
  });

  const getErrorMessage = (error: unknown) => {
    if (axios.isAxiosError(error)) {
      const detail = error.response?.data?.detail;
      if (typeof detail === 'string') return detail;
    }
    return 'Credenciales incorrectas';
  };

  const onSubmit = async (data: LoginForm) => {
    setErrorMessage(null);
    try {
      const user = await login(data.email, data.password);
      navigate(from ?? getHomePath(user.role), { replace: true });
    } catch (error) {
      setErrorMessage(getErrorMessage(error));
    }
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
          <div className="flex flex-col items-center mb-8">
            <span className="relative inline-block w-20 h-20 mb-4 text-gray-400">
              <Settings className="absolute left-0 top-0 w-20 h-20" />
              <Wrench className="absolute left-[25px] top-[25px] w-10 h-10 text-primary-red -rotate-15" />
            </span>
            <h1 className="text-3xl font-bold tracking-tight text-white">
              Sistema Mecánico
            </h1>
            <p className="text-text-muted text-base mt-2">
              Taller de Integración II • UCT
            </p>
          </div>

          <div className="bg-black/40 p-7 rounded-xl border border-border-custom">
            <h3 className="mb-6 text-lg text-white font-semibold">
              Iniciar Sesión
            </h3>

            <form onSubmit={handleSubmit(onSubmit)}>
              <Input
                label="Correo Electrónico"
                type="email"
                placeholder="correo@ejemplo.com"
                icon={<Mail className="w-5 h-5" />}
                error={errors.email?.message}
                {...register('email')}
              />

              <div className="relative">
                <Input
                  label="Contraseña"
                  type={showPassword ? 'text' : 'password'}
                  placeholder="••••••••"
                  icon={<Lock className="w-5 h-5" />}
                  error={errors.password?.message}
                  {...register('password')}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-4 top-[42px] text-text-muted hover:text-white transition-colors bg-transparent border-none cursor-pointer"
                >
                  {showPassword ? (
                    <EyeOff className="w-5 h-5" />
                  ) : (
                    <Eye className="w-5 h-5" />
                  )}
                </button>
              </div>

              <Button
                type="submit"
                isLoading={isLoading}
                className="w-full py-4 text-lg mt-2"
              >
                Ingresar a mi cuenta
              </Button>

              {errorMessage && (
                <div className="flex items-center justify-center gap-2 mt-4 text-status-red text-sm bg-status-red/10 border border-status-red/40 rounded-lg px-4 py-3">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  {errorMessage}
                </div>
              )}
            </form>
          </div>
        </GlassCard>
      </div>
    </div>
  );
}
