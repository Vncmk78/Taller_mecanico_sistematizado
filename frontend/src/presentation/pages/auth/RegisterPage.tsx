import { useRef, useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useForm, type UseFormSetError } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import axios from 'axios';
import { Mail, Lock, User as UserIcon, Phone, Eye, EyeOff, Settings, Wrench } from 'lucide-react';
import { Button } from '@/presentation/components/ui/Button';
import { Input } from '@/presentation/components/ui/Input';
import { GlassCard } from '@/presentation/components/ui/GlassCard';
import { Alert } from '@/presentation/components/ui/Alert';
import { authService } from '@/infrastructure/api/AuthService';
import { getApiErrorMessage, isConflictError, isOfflineError } from '@/infrastructure/api/errors';
import { usePerfilClienteStore } from '@/infrastructure/stores/usePerfilClienteStore';

// Validaciones de ayuda para el visitante. La autoridad es MS1: sus límites
// (correo válido, contraseña >= 8 tras quitar espacios exteriores, nombre de 2
// a 120) se repiten aquí solo para avisar antes, y su 422 se sigue mostrando.
const registerSchema = z
  .object({
    full_name: z
      .string()
      .trim()
      .min(2, 'El nombre debe tener al menos 2 caracteres')
      .max(120, 'El nombre puede tener hasta 120 caracteres'),
    email: z.string().trim().email('Ingrese un correo válido'),
    password: z
      .string()
      .refine((v) => v.trim().length >= 8, 'La contraseña debe tener al menos 8 caracteres'),
    confirmPassword: z.string(),
    telefono: z.string().trim().max(30, 'El teléfono puede tener hasta 30 caracteres').optional(),
  })
  .refine((d) => d.password === d.confirmPassword, {
    path: ['confirmPassword'],
    message: 'Las contraseñas no coinciden',
  });

type RegisterForm = z.infer<typeof registerSchema>;
type CampoApi = 'full_name' | 'email' | 'password';

const MENSAJE_422: Record<CampoApi, string> = {
  full_name: 'El nombre debe tener entre 2 y 120 caracteres',
  email: 'Ingrese un correo válido',
  password: 'La contraseña debe tener al menos 8 caracteres',
};

function esCampoApi(valor: unknown): valor is CampoApi {
  return valor === 'full_name' || valor === 'email' || valor === 'password';
}

/**
 * Traslada a cada campo los errores 422 de FastAPI (`detail[].loc`). Devuelve
 * false si no se pudo asociar ninguno, para mostrar un mensaje general.
 */
function aplicarErroresDeCampo(error: unknown, setError: UseFormSetError<RegisterForm>): boolean {
  if (!axios.isAxiosError(error) || error.response?.status !== 422) return false;
  const detail = (error.response.data as { detail?: unknown } | undefined)?.detail;
  if (!Array.isArray(detail)) return false;
  let aplicado = false;
  for (const item of detail) {
    const loc = (item as { loc?: unknown })?.loc;
    const campo: unknown = Array.isArray(loc) ? loc[loc.length - 1] : undefined;
    if (esCampoApi(campo)) {
      setError(campo, { type: 'server', message: MENSAJE_422[campo] });
      aplicado = true;
    }
  }
  return aplicado;
}

export function RegisterPage() {
  const navigate = useNavigate();
  const recordarTelefono = usePerfilClienteStore((s) => s.recordarTelefono);
  const [showPassword, setShowPassword] = useState(false);
  const [errorGeneral, setErrorGeneral] = useState<string | null>(null);
  // Bloqueo síncrono: impide un segundo envío antes de que React vuelva a
  // renderizar con el botón deshabilitado (doble clic o Enter repetido).
  const enviando = useRef(false);
  // Estado visible del envío. No se usa `isSubmitting` de react-hook-form
  // porque un envío repetido e ignorado lo devuelve a false antes de tiempo.
  const [creando, setCreando] = useState(false);

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<RegisterForm>({ resolver: zodResolver(registerSchema) });

  const onSubmit = async (data: RegisterForm) => {
    if (enviando.current) return;
    enviando.current = true;
    setCreando(true);
    setErrorGeneral(null);
    try {
      // Solo nombre, correo y contraseña: el rol Cliente lo asigna el servidor.
      await authService.register({
        full_name: data.full_name,
        email: data.email,
        password: data.password,
      });
      recordarTelefono(data.email, data.telefono);
      navigate('/login', { replace: true, state: { registro: { email: data.email } } });
    } catch (error) {
      if (isConflictError(error)) {
        setError('email', {
          type: 'server',
          message: 'Este correo ya está registrado. Inicia sesión o usa otro correo.',
        });
      } else if (aplicarErroresDeCampo(error, setError)) {
        // Errores mostrados junto a cada campo.
      } else if (isOfflineError(error)) {
        setErrorGeneral(
          'No se pudo conectar con el servidor. Si el problema persiste, intenta iniciar ' +
            'sesión: es posible que la cuenta se haya creado.'
        );
      } else {
        setErrorGeneral(getApiErrorMessage(error, 'No fue posible crear la cuenta.'));
      }
    } finally {
      enviando.current = false;
      setCreando(false);
    }
  };

  // El envío se arma dentro del manejador del evento (no durante el render).
  const enviarFormulario = (event: FormEvent<HTMLFormElement>) => {
    if (enviando.current) {
      event.preventDefault();
      return;
    }
    void handleSubmit(onSubmit)(event);
  };

  return (
    <div className="min-h-screen flex flex-col animate-fade-in">
      <nav className="flex justify-between items-center gap-3 px-4 sm:px-8 lg:px-12 py-4 lg:py-5 border-b border-border-custom bg-surface sticky top-0 z-50">
        <Link to="/" className="flex items-center gap-2.5 text-xl sm:text-2xl font-bold no-underline text-text-main">
          <span aria-hidden className="relative inline-block w-[35px] h-[35px] text-text-muted">
            <Settings className="absolute left-0 top-0 w-6 h-6" />
            <Wrench className="absolute left-3 top-3 w-4 h-4 text-primary-orange -rotate-15" />
          </span>
          TallerConect
        </Link>
        <Link
          to="/login"
          className="bg-primary-blue text-white px-4 sm:px-6 py-2.5 sm:py-3 rounded-lg font-bold text-sm sm:text-base transition-all duration-300 hover:bg-primary-blue-hover no-underline whitespace-nowrap"
        >
          Iniciar sesión
        </Link>
      </nav>

      <main
        id="contenido-principal"
        tabIndex={-1}
        className="flex flex-col items-center justify-center flex-grow px-5 py-8 focus:outline-none"
      >
        <GlassCard className="w-full max-w-[520px] p-6 sm:p-[40px_40px] text-center">
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-text-main mb-2">
            Crear cuenta de cliente
          </h1>
          <p className="text-text-muted text-sm mb-6">
            Registra tu cuenta para inscribir tus vehículos y seguir sus atenciones.
          </p>

          <div className="bg-bg-secondary p-6 sm:p-7 rounded-xl border border-border-custom text-left">
            <form onSubmit={enviarFormulario} noValidate aria-label="Registro de cliente">
              <Input
                label="Nombre completo"
                autoComplete="name"
                placeholder="Ana Pérez"
                icon={<UserIcon className="w-5 h-5" />}
                error={errors.full_name?.message}
                {...register('full_name')}
              />
              <Input
                label="Correo Electrónico"
                type="email"
                autoComplete="email"
                placeholder="correo@ejemplo.com"
                icon={<Mail className="w-5 h-5" />}
                error={errors.email?.message}
                {...register('email')}
              />
              <div className="relative">
                <Input
                  label="Contraseña"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="new-password"
                  placeholder="Mínimo 8 caracteres"
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
                  {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
              <Input
                label="Confirmar contraseña"
                type={showPassword ? 'text' : 'password'}
                autoComplete="new-password"
                placeholder="Repite la contraseña"
                icon={<Lock className="w-5 h-5" />}
                error={errors.confirmPassword?.message}
                {...register('confirmPassword')}
              />
              <Input
                label="Teléfono de contacto (opcional)"
                type="tel"
                autoComplete="tel"
                placeholder="+56 9 1234 5678"
                icon={<Phone className="w-5 h-5" />}
                error={errors.telefono?.message}
                {...register('telefono')}
              />

              <Button
                type="submit"
                variant="accent"
                isLoading={creando}
                className="w-full py-4 text-lg mt-2"
              >
                Crear mi cuenta
              </Button>

              {errorGeneral && (
                <Alert tone="error" className="mt-4">
                  {errorGeneral}
                </Alert>
              )}
            </form>
          </div>

          <p className="mt-6 text-sm text-text-muted">
            ¿Ya tienes cuenta?{' '}
            <Link to="/login" className="text-primary-blue font-semibold">
              Inicia sesión
            </Link>
          </p>
        </GlassCard>
      </main>
    </div>
  );
}
