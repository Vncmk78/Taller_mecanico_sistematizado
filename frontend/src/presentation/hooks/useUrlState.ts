import { useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';

type Parser<T> = (value: string | null) => T;
type Serializer<T> = (value: T) => string | null;

interface UseUrlStateOptions<T> {
  defaultValue: T;
  parse?: Parser<T>;
  serialize?: Serializer<T>;
  replace?: boolean;
}

export function useUrlState<T>(key: string, options: UseUrlStateOptions<T>) {
  const { defaultValue, parse, serialize, replace = true } = options;
  const [searchParams, setSearchParams] = useSearchParams();

  const value = useMemo(() => {
    const raw = searchParams.get(key);
    if (raw === null) return defaultValue;
    if (parse) return parse(raw);
    return raw as unknown as T;
  }, [searchParams, key, defaultValue, parse]);

  const setValue = useCallback(
    (next: T | ((prev: T) => T), relatedParams: Readonly<Record<string, string | null>> = {}) => {
      const resolved = typeof next === 'function' ? (next as (prev: T) => T)(value) : next;
      const nextParams = new URLSearchParams(searchParams);

      if (serialize) {
        const serialized = serialize(resolved);
        if (serialized === null || serialized === '' || serialized === String(defaultValue)) {
          nextParams.delete(key);
        } else {
          nextParams.set(key, serialized);
        }
      } else {
        const str = String(resolved);
        if (str === '' || str === String(defaultValue)) {
          nextParams.delete(key);
        } else {
          nextParams.set(key, str);
        }
      }

      // Actualiza los parámetros relacionados en una sola navegación. Varias
      // llamadas a useSearchParams en el mismo evento no acumulan sus cambios.
      for (const [relatedKey, relatedValue] of Object.entries(relatedParams)) {
        if (relatedValue === null || relatedValue === '') nextParams.delete(relatedKey);
        else nextParams.set(relatedKey, relatedValue);
      }
      setSearchParams(nextParams, { replace });
    },
    [searchParams, setSearchParams, key, value, serialize, defaultValue, replace]
  );

  return [value, setValue] as const;
}

export function parseNumberOrDefault(fallback: number) {
  return (raw: string | null): number => {
    if (raw === null || raw.trim() === '') return fallback;
    const parsed = Number(raw);
    if (Number.isNaN(parsed) || parsed < 1) return fallback;
    return Math.floor(parsed);
  };
}

export function serializeNumber(value: number): string | null {
  if (value < 1) return null;
  return String(value);
}

export function parseStringOrDefault(fallback: string) {
  return (raw: string | null): string => {
    if (raw === null) return fallback;
    return raw;
  };
}

export function serializeString(value: string): string | null {
  if (value.trim() === '') return null;
  return value;
}
