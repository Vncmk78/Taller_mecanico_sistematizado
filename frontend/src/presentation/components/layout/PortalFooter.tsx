import { Link } from 'react-router-dom';

export function PortalFooter() {
  return (
    <footer className="border-t border-border-custom bg-surface px-4 py-3 text-center text-xs text-text-muted sm:px-8">
      <p>
        TallerConect ·{' '}
        <Link
          to="/cookies"
          className="font-bold text-primary-blue underline underline-offset-2"
        >
          Política de cookies
        </Link>
      </p>
    </footer>
  );
}
