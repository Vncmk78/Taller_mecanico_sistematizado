/// <reference types="node" />
import { readFileSync, readdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import * as ts from 'typescript';
import { describe, expect, it } from 'vitest';

/**
 * Verificación de contratos (Semana 10): toda llamada HTTP de la capa
 * `src/infrastructure/api/` debe corresponder a una operación publicada por la
 * API Gateway en el OpenAPI congelado `backend/docs/openapi/sgtm-gateway-3.0.0.json`.
 *
 * La prueba recorre el AST de TypeScript para no depender de coincidencias de
 * texto: resuelve literales, plantillas y constantes de módulo. Un endpoint
 * nuevo, un método equivocado o una llamada dinámica sin ruta conocida hacen
 * fallar la suite.
 */

const API_DIR = dirname(fileURLToPath(import.meta.url));
const OPENAPI = join(API_DIR, '../../../../backend/docs/openapi/sgtm-gateway-3.0.0.json');
const METODOS = new Set(['get', 'post', 'put', 'patch', 'delete']);

interface Llamada {
  archivo: string;
  metodo: string;
  ruta: string | null;
  argumento: string;
}

interface DocumentoOpenApi {
  paths: Record<string, Record<string, unknown>>;
}

function canonizar(ruta: string): string {
  const conApi = ruta.startsWith('/api/') ? ruta : '/api' + ruta;
  return conApi.replace(/\{[^}]*\}/g, '{}');
}

/** Texto de la ruta si es un literal, plantilla o constante resoluble. */
function textoLiteral(nodo: ts.Node, constantes: Map<string, string>): string | null {
  if (ts.isStringLiteral(nodo) || ts.isNoSubstitutionTemplateLiteral(nodo)) return nodo.text;
  if (ts.isTemplateExpression(nodo)) {
    let texto = nodo.head.text;
    for (const parte of nodo.templateSpans) texto += '{}' + parte.literal.text;
    return texto;
  }
  if (ts.isIdentifier(nodo) && constantes.has(nodo.text)) return constantes.get(nodo.text)!;
  return null;
}

function extraerLlamadas(): Llamada[] {
  const archivos = readdirSync(API_DIR).filter(
    (nombre) => nombre.endsWith('.ts') && !nombre.endsWith('.test.ts')
  );
  const llamadas: Llamada[] = [];

  for (const archivo of archivos) {
    const completo = join(API_DIR, archivo);
    const fuente = ts.createSourceFile(
      completo,
      readFileSync(completo, 'utf8'),
      ts.ScriptTarget.Latest,
      true
    );

    // Constantes de módulo con rutas, por ejemplo RUTA_CUPO.
    const constantes = new Map<string, string>();
    const recolectar = (nodo: ts.Node): void => {
      if (
        ts.isVariableDeclaration(nodo) &&
        ts.isIdentifier(nodo.name) &&
        nodo.initializer
      ) {
        const texto = textoLiteral(nodo.initializer, constantes);
        if (texto) constantes.set(nodo.name.text, texto);
      }
      ts.forEachChild(nodo, recolectar);
    };
    recolectar(fuente);

    const visitar = (nodo: ts.Node): void => {
      if (ts.isCallExpression(nodo) && ts.isPropertyAccessExpression(nodo.expression)) {
        const objeto = nodo.expression.expression;
        const metodo = nodo.expression.name.text;
        const primerArgumento = nodo.arguments[0];

        if (primerArgumento) {
          const argumento = primerArgumento.getText(fuente);
          if (
            ts.isIdentifier(objeto) &&
            objeto.text === 'apiClient' &&
            METODOS.has(metodo)
          ) {
            llamadas.push({
              archivo,
              metodo,
              ruta: textoLiteral(primerArgumento, constantes),
              argumento,
            });
          }
          // `this.operacionGuardada(ruta, body)` es el envoltorio de
          // PresupuestoService; sus rutas también son parte del contrato.
          if (objeto.kind === ts.SyntaxKind.ThisKeyword && metodo === 'operacionGuardada') {
            llamadas.push({
              archivo,
              metodo: 'post',
              ruta: textoLiteral(primerArgumento, constantes),
              argumento,
            });
          }
        }
      }
      ts.forEachChild(nodo, visitar);
    };
    visitar(fuente);
  }

  return llamadas;
}

const documento = JSON.parse(readFileSync(OPENAPI, 'utf8')) as DocumentoOpenApi;
const operaciones = new Set<string>();
for (const [ruta, metodos] of Object.entries(documento.paths)) {
  for (const metodo of Object.keys(metodos)) {
    if (METODOS.has(metodo)) operaciones.add(metodo.toUpperCase() + ' ' + canonizar(ruta));
  }
}

const llamadas = extraerLlamadas();
const estaticas = llamadas.filter((llamada) => llamada.ruta !== null);
const dinamicas = llamadas.filter((llamada) => llamada.ruta === null);

describe('contratos de la API Gateway usados por el frontend', () => {
  it('resuelve al menos una llamada estática por servicio', () => {
    expect(estaticas.length).toBeGreaterThan(0);
  });

  it('todas las rutas y métodos usados existen en el OpenAPI de la Gateway', () => {
    const inexistentes = estaticas
      .map((llamada) => ({
        ...llamada,
        clave: llamada.metodo.toUpperCase() + ' ' + canonizar(llamada.ruta!),
      }))
      .filter((llamada) => !operaciones.has(llamada.clave))
      .map((llamada) => `${llamada.archivo}: ${llamada.clave}`);

    expect(inexistentes).toEqual([]);
  });

  it('no deja llamadas dinámicas sin resolver fuera de envoltorios conocidos', () => {
    // Excepciones conocidas:
    // - PresupuestoService.operacionGuardada: recibe rutas literales en los
    //   puntos de llamada; internamente hace apiClient.post(ruta).
    // - paginacion.ts: recorre páginas llamando apiClient.get(url) donde url
    //   proviene de servicios que ya se validan en sus llamadas estáticas.
    const inesperadas = dinamicas
      .filter((llamada) => {
        if (llamada.archivo === 'PresupuestoService.ts' && llamada.argumento === 'ruta') return false;
        if (llamada.archivo === 'paginacion.ts' && llamada.argumento === 'url') return false;
        return true;
      })
      .map((llamada) => `${llamada.archivo}: ${llamada.metodo.toUpperCase()}(${llamada.argumento})`);

    expect(inesperadas).toEqual([]);
  });

  it('el envoltorio operacionGuardada solo se invoca con rutas publicadas', () => {
    const rutasEnvoltorio = estaticas.filter(
      (llamada) => llamada.archivo === 'PresupuestoService.ts' && llamada.argumento.startsWith('`/presupuestos/')
    );
    expect(rutasEnvoltorio.length).toBeGreaterThan(0);
    for (const llamada of rutasEnvoltorio) {
      const clave = llamada.metodo.toUpperCase() + ' ' + canonizar(llamada.ruta!);
      expect(operaciones.has(clave), `${llamada.archivo}: ${clave}`).toBe(true);
    }
  });
});
