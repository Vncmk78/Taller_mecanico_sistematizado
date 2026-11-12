import { useEffect, useRef } from 'react';
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
  const asideRef = useRef<HTMLElement>(null);

  useEffect(() => {
    if (!open) return;
    const aside = asideRef.current;
    const focusable = aside?.querySelectorAll<HTMLElement>(
      'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])',
    );
    focusable?.[0]?.focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose?.();
        return;
      }
      if (event.key !== 'Tab' || !focusable || focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      const trigger = document.querySelector<HTMLElement>('[aria-controls="navegacion-lateral"]');
      trigger?.focus();
    };
  }, [open, onClose]);

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
        ref={asideRef}
        id="navegacion-lateral"
        aria-label="Menú lateral"
        aria-modal={open ? true : undefined}
        role={open ? 'dialog' : undefined}
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
