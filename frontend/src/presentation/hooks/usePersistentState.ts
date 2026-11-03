import { useCallback, useEffect, useState } from 'react';

type StorageType = 'local' | 'session';

function getStorage(type: StorageType): Storage {
  if (typeof window === 'undefined') {
    return {
      getItem: () => null,
      setItem: () => undefined,
      removeItem: () => undefined,
      clear: () => undefined,
      key: () => null,
      length: 0,
    } as Storage;
  }
  return type === 'session' ? window.sessionStorage : window.localStorage;
}

export function usePersistentState<T>(
  key: string,
  defaultValue: T,
  storageType: StorageType = 'local'
): [T, (value: T | ((prev: T) => T)) => void, () => void] {
  const storage = getStorage(storageType);

  const [value, setValue] = useState<T>(() => {
    try {
      const raw = storage.getItem(key);
      if (raw === null) return defaultValue;
      return JSON.parse(raw) as T;
    } catch {
      return defaultValue;
    }
  });

  useEffect(() => {
    try {
      storage.setItem(key, JSON.stringify(value));
    } catch {
      // Ignorar errores de cuota/privacidad
    }
  }, [key, value, storage]);

  const clear = useCallback(() => {
    try {
      storage.removeItem(key);
    } catch {
      // Ignorar
    }
    setValue(defaultValue);
  }, [key, defaultValue, storage]);

  return [value, setValue, clear];
}
