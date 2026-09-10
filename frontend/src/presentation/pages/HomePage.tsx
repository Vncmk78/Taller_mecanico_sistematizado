import { Link } from 'react-router-dom';
import {
  Settings,
  Wrench,
  Shield,
  Search,
  Camera,
  Phone,
  Mail,
} from 'lucide-react';

const features = [
  {
    icon: <Shield className="w-6 h-6" />,
    title: 'Transparencia Total',
    description:
      'El cliente siempre sabrá qué repuesto se instaló, su precio exacto y si proviene de un distribuidor oficial o genérico.',
  },
  {
    icon: <Search className="w-6 h-6" />,
    title: 'Trazabilidad Completa',
    description:
      'Historial inmutable de cada vehículo. Busque por patente y vea instantáneamente mantenciones pasadas.',
  },
  {
    icon: <Camera className="w-6 h-6" />,
    title: 'Evidencia Visual',
    description:
      'Los mecánicos suben fotos y videos del diagnóstico a la plataforma para que apruebe el presupuesto con confianza.',
  },
  {
    icon: <Wrench className="w-6 h-6" />,
    title: 'Flujo Secuencial',
    description:
      'Control estricto de estados: Recibido → Diagnóstico → Esperando Repuestos → Reparación → Listo.',
  },
];

const steps = [
  {
    number: 1,
    title: 'Ingreso',
    description:
      'El cliente reserva hora o ingresa presencialmente. Se crea la orden y se asigna mecánico.',
  },
  {
    number: 2,
    title: 'Diagnóstico',
    description:
      'El mecánico revisa el auto, sube fotos y arma la cotización de repuestos y mano de obra.',
  },
  {
    number: 3,
    title: 'Aprobación',
    description:
      'El cliente recibe una notificación, revisa la evidencia en su celular y aprueba con 1 clic.',
  },
  {
    number: 4,
    title: 'Entrega',
    description:
      'Se realiza el trabajo con los repuestos solicitados. El auto pasa a estado "Listo".',
  },
];

export function HomePage() {
  return (
    <div className="min-h-screen flex flex-col animate-fade-in">
      <nav className="flex justify-between items-center px-12 py-5 border-b border-border-custom bg-black/80 backdrop-blur-[10px] sticky top-0 z-50">
        <div className="flex items-center gap-2.5 text-2xl font-bold text-white">
          <span className="relative inline-block w-[35px] h-[35px] text-gray-400">
            <Settings className="absolute left-0 top-0 w-6 h-6" />
            <Wrench className="absolute left-3 top-3 w-4 h-4 text-primary-red -rotate-15" />
          </span>
          Sistema Mecánico
        </div>
        <div className="flex gap-6">
          <a href="#" className="text-text-muted text-sm hover:text-white transition-colors">
            Inicio
          </a>
          <a href="#" className="text-text-muted text-sm hover:text-white transition-colors">
            Quiénes Somos
          </a>
          <a href="#" className="text-text-muted text-sm hover:text-white transition-colors">
            Servicios
          </a>
          <a href="#" className="text-text-muted text-sm hover:text-white transition-colors">
            Contacto
          </a>
        </div>
        <Link
          to="/login"
          className="bg-primary-red text-white px-6 py-3 rounded-lg font-bold text-base transition-all duration-300 shadow-[0_4px_15px_rgba(211,47,47,0.3)] hover:bg-primary-red-hover hover:-translate-y-0.5 no-underline flex items-center gap-2"
        >
          Ingresar al Portal
        </Link>
      </nav>

      <section className="text-center py-[120px] px-5 pb-20 flex flex-col items-center">
        <div className="text-[90px] text-white/90 mb-5 drop-shadow-[0_0_30px_rgba(255,255,255,0.1)]">
          <Settings className="w-[90px] h-[90px]" />
        </div>
        <h1 className="text-6xl font-extrabold mb-5 tracking-tight">
          El taller del futuro,{' '}
          <span className="text-primary-red">hoy.</span>
        </h1>
        <p className="text-text-muted text-xl mb-10 max-w-[700px] leading-relaxed">
          Digitalizamos la gestión integral de talleres mecánicos. Conectamos
          la eficiencia operativa del administrador con la tranquilidad y
          transparencia que exige el cliente.
        </p>
        <Link
          to="/login"
          className="bg-primary-red text-white px-8 py-4 rounded-lg font-bold text-xl transition-all duration-300 shadow-[0_4px_15px_rgba(211,47,47,0.3)] hover:bg-primary-red-hover hover:-translate-y-0.5 no-underline"
        >
          Comenzar Ahora
        </Link>
      </section>

      <h2 className="text-center text-4xl mb-12 mt-10">
        ¿Por qué elegir nuestro sistema?
      </h2>
      <section className="grid grid-cols-4 gap-5 px-12 mb-24">
        {features.map((feature) => (
          <div
            key={feature.title}
            className="glass-card text-left p-10 hover:-translate-y-2.5 hover:border-primary-red/50 hover:shadow-[0_15px_40px_rgba(0,0,0,0.6)] transition-all duration-300"
          >
            <div className="w-[55px] h-[55px] rounded-xl bg-primary-red/15 text-primary-red flex items-center justify-center mb-6 border border-primary-red/30 text-2xl">
              {feature.icon}
            </div>
            <h3 className="text-xl font-semibold mb-3">{feature.title}</h3>
            <p className="text-text-muted">{feature.description}</p>
          </div>
        ))}
      </section>

      <section className="py-15 px-12 bg-black/40 border-y border-border-custom mb-20">
        <h2 className="text-center text-4xl mb-12 mt-0">
          ¿Cómo funciona el flujo?
        </h2>
        <div className="grid grid-cols-4 gap-5 max-w-[1200px] mx-auto">
          {steps.map((step) => (
            <div key={step.number} className="text-center p-5">
              <div className="w-[60px] h-[60px] rounded-full bg-primary-red text-white flex items-center justify-center text-2xl font-bold mx-auto mb-5 shadow-[0_0_20px_rgba(211,47,47,0.4)]">
                {step.number}
              </div>
              <h3 className="mb-2.5">{step.title}</h3>
              <p className="text-text-muted">{step.description}</p>
            </div>
          ))}
        </div>
      </section>

      <footer className="flex justify-between items-center px-12 py-10 bg-black/95 text-text-muted text-sm">
        <div className="flex items-center gap-2.5 text-xl">
          <span className="relative inline-block w-[28px] h-[28px] text-gray-400 scale-80">
            <Settings className="absolute left-0 top-0 w-5 h-5" />
            <Wrench className="absolute left-2.5 top-2.5 w-3 h-3 text-primary-red -rotate-15" />
          </span>
          Sistema Mecánico
        </div>
        <div className="text-right leading-relaxed">
          Soporte Técnico y Ventas
          <br />
          <Phone className="w-5 inline text-text-muted mr-1" /> +443 379 771
          <br />
          <Mail className="w-5 inline text-text-muted mr-1" />{' '}
          mecanica@sistema.cl
        </div>
      </footer>
    </div>
  );
}
