// Integración de la capa Web (Semana 8): el frontend real en un navegador real
// (Chromium headless) contra la Gateway y los microservicios levantados.
//
// Por cada rol inicia sesión desde /login, comprueba que la app redirige a su
// portal, abre una vista que consume la API y verifica que las llamadas HTTP
// del navegador pasan por /api (proxy de Vite o Nginx → Gateway) y responden 2xx.
// No crea ni modifica datos.
//
// Requisitos: el frontend servido (npm run dev o la imagen Nginx) apuntando a
// la Gateway, las cuentas de scripts/seed_usuarios_prueba.py y Playwright
// disponible sin agregarlo a package.json:
//   npm i --no-save playwright && npx playwright install chromium
//
// Uso:  WEB_URL=http://localhost:5173 node scripts/integracion-web.mjs [carpeta-capturas]
// Sale con 0 si todos los roles pasan.
import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';

const WEB_URL = process.env.WEB_URL ?? 'http://localhost:5173';
const CAPTURAS = process.argv[2];

const ROLES = [
  { rol: 'cliente', email: 'cliente@pruebas.cl', clave: 'ClientePrueba123!', portal: '/client',
    vista: '/client/vehiculos', api: '/api/vehiculos' },
  { rol: 'mecanico', email: 'mecanico@pruebas.cl', clave: 'MecanicoPrueba123!', portal: '/mechanic',
    vista: '/mechanic/ordenes', api: '/api/ordenes' },
  { rol: 'administrador', email: 'administrador@pruebas.cl', clave: 'AdminPrueba123!', portal: '/admin',
    vista: '/admin/ordenes', api: '/api/ordenes' },
];

if (CAPTURAS) mkdirSync(CAPTURAS, { recursive: true });
const navegador = await chromium.launch();
const resultados = [];

for (const caso of ROLES) {
  const contexto = await navegador.newContext();
  const pagina = await contexto.newPage();
  const llamadas = [];
  pagina.on('response', (r) => {
    const url = new URL(r.url());
    if (url.pathname.startsWith('/api/')) llamadas.push(`${r.request().method()} ${url.pathname} ${r.status()}`);
  });
  const fila = { rol: caso.rol, login: '', portal: '', vista: '', errores: [] };
  try {
    await pagina.goto(`${WEB_URL}/login`, { waitUntil: 'networkidle' });
    await pagina.getByPlaceholder('correo@ejemplo.com').fill(caso.email);
    await pagina.getByPlaceholder('••••••••').fill(caso.clave);
    const login = pagina.waitForResponse((r) => r.url().endsWith('/api/auth/login'));
    await pagina.locator('button[type="submit"]').click();
    fila.login = String((await login).status());
    await pagina.waitForURL((u) => u.pathname.startsWith(caso.portal), { timeout: 30000 });
    fila.portal = new URL(pagina.url()).pathname;
    // Navegación como la hace el usuario: clic en el enlace del menú del portal.
    const datos = pagina.waitForResponse(
      (r) => new URL(r.url()).pathname === caso.api && r.request().method() === 'GET',
      { timeout: 90000 },
    );
    await pagina.locator(`a[href="${caso.vista}"]`).first().click();
    await pagina.waitForURL((u) => u.pathname === caso.vista, { timeout: 30000 });
    fila.vista = String((await datos).status());
    await pagina.waitForLoadState('networkidle', { timeout: 60000 });
    if (CAPTURAS) await pagina.screenshot({ path: `${CAPTURAS}/${caso.rol}.png`, fullPage: true });
  } catch (error) {
    fila.errores.push(String(error.message ?? error).split('\n')[0]);
  }
  const fallidas = llamadas.filter((l) => !/ 2\d\d$/.test(l));
  if (fallidas.length) fila.errores.push(`llamadas no 2xx: ${fallidas.join(', ')}`);
  if (fila.login !== '200') fila.errores.push(`login respondió ${fila.login || 'nada'}`);
  if (!fila.portal.startsWith(caso.portal)) fila.errores.push(`portal ${fila.portal || '—'}`);
  if (fila.vista !== '200') fila.errores.push(`${caso.api} respondió ${fila.vista || 'nada'}`);
  fila.llamadas = llamadas.length;
  resultados.push(fila);
  await contexto.close();
}
await navegador.close();

console.log('| Rol | Login | Portal | Vista con datos | Llamadas /api | Resultado |');
console.log('|---|---|---|---|---:|---|');
for (const f of resultados) {
  const r = f.errores.length ? `FALLA: ${f.errores.join('; ')}` : 'OK';
  console.log(`| ${f.rol} | ${f.login} | ${f.portal} | ${f.vista} | ${f.llamadas} | ${r} |`);
}
process.exit(resultados.every((f) => f.errores.length === 0) ? 0 : 1);
