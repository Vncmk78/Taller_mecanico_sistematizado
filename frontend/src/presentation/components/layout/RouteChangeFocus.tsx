import { useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';

const TARGET_ID = 'contenido-principal';

export function RouteChangeFocus() {
  const { pathname } = useLocation();
  const isFirstRender = useRef(true);

  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }

    const target = document.getElementById(TARGET_ID);
    if (target) {
      target.focus({ preventScroll: true });
    }
  }, [pathname]);

  return null;
}