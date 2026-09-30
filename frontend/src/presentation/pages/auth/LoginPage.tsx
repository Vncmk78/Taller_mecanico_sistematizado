import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import axios from 'axios';
import { Mail, Lock, Eye, EyeOff, Settings, Wrench } from 'lucide-react';
import { Button } from '@/presentation/components/ui/Button';
import { Input } from '@/presentation/components/ui/Input';
import { GlassCard } from '@/presentation/components/ui/GlassCard';
import { Alert } from '@/presentation/components/ui/Alert';
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
      <nav className="flex justify-between items-center px-12 py-5 border-b border-border-custom bg-surface sticky top-0 z-50">
        <Link to="/" className="flex items-center gap-2.5 text-2xl font-bold no-underline text-text-main">
          <span className="relative inline-block w-[35px] h-[35px] text-text-muted">
            <Settings className="absolute left-0 top-0 w-6 h-6" />
            <Wrench className="absolute left-3 top-3 w-4 h-4 text-primary-orange -rotate-15" />
          </span>
          TallerConect
        </Link>
        <Link
          to="/"
          className="bg-primary-blue text-white px-6 py-3 rounded-lg font-bold text-base transition-all duration-300 shadow-[0_4px_15px_rgba(21,40,63,0.25)] hover:bg-primary-blue-hover hover:-translate-y-0.5 no-underline flex items-center gap-2"
        >
          Volver al Inicio
        </Link>
      </nav>

      <div className="flex flex-col items-center justify-center flex-grow px-5 py-8">
        <GlassCard className="w-full max-w-[480px] p-[50px_40px] text-center">
          <div className="flex flex-col items-center mb-8">
            <span className="relative inline-block w-20 h-20 mb-4 text-text-muted">
              <Settings className="absolute left-0 top-0 w-20 h-20" />
              <Wrench className="absolute left-[25px] top-[25px] w-10 h-10 text-primary-orange -rotate-15" />
            </span>
            <h1 className="text-3xl font-bold tracking-tight text-text-main">
              TallerConect
            </h1>
          </div>

          <div className="bg-bg-secondary p-7 rounded-xl border border-border-custom">
            <h3 className="mb-6 text-lg text-text-main font-semibold">
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
                  aria-label={showPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'}
                  aria-pressed={showPassword}
                  className="absolute right-4 top-[42px] text-text-muted hover:text-primary-blue transition-colors bg-transparent border-none cursor-pointer"
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
                variant="accent"
                isLoading={isLoading}
                className="w-full py-4 text-lg mt-2"
              >
                Ingresar a mi cuenta
              </Button>

              {errorMessage && (
                <Alert tone="error" className="mt-4 justify-center">
                  {errorMessage}
                </Alert>
              )}
            </form>
          </div>
        </GlassCard>
      </div>
    </div>
  );
}
