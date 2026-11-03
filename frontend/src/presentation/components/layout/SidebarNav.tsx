import { X } from 'lucide-react';
import { AppBrand } from '@/presentation/components/layout/AppBrand';
import { AppNavLink, type NavSection } from '@/presentation/components/layout/AppNavLink';

interface SidebarNavProps {
  sections: NavSection[];
  /** En móvil controla si el panel lateral está desplegado. */
  open?: boolean;
  onClose?: () => void;
}

export function SidebarNav({ sections, open = false, onClose }: SidebarNavProps) {
  return (
    <>
      {open && (
        <button
          type="button"
          aria-label="Cerrar menú de navegación"
          onClick={onClose}
          className="fixed inset-0 z-30 bg-black/50 lg:hidden"
        />
      )}
      <aside
        id="navegacion-lateral"
        aria-label="Menú lateral"
        className={`fixed inset-y-0 left-0 z-40 flex w-[280px] max-w-[85vw] flex-col border-r border-[#0B1017] bg-primary-blue transition-transform duration-300 lg:sticky lg:top-0 lg:z-10 lg:h-screen lg:translate-x-0 lg:shrink-0 ${
          open ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex items-center justify-between gap-2.5 border-b border-white/10 p-5 sm:p-7">
          <AppBrand />
          <button
            type="button"
            aria-label="Cerrar menú lateral"
            onClick={onClose}
            className="rounded-lg p-1.5 text-[#CBD5E1] transition-colors hover:bg-white/10 hover:text-white lg:hidden"
          >
            <X className="h-5 w-5" aria-hidden />
          </button>
        </div>

        <nav aria-label="Navegación de sesión" className="flex flex-grow flex-col gap-2 overflow-y-auto p-5">
          {sections.map((section, indice) => (
            <div key={section.title ?? `seccion-${indice}`} className="flex flex-col">
              {section.title && (
                <div className="mx-4 mb-2 mt-4 text-xs font-bold uppercase tracking-[1.5px] text-[#64748B]">
                  {section.title}
                </div>
              )}
              {section.items.map((item) => (
                <AppNavLink key={item.to} variant="sidebar" onNavigate={onClose} {...item} />
              ))}
            </div>
          ))}
        </nav>
      </aside>
    </>
  );
}
