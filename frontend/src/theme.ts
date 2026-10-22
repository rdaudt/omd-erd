export const THEME_STORAGE_KEY = 'omd-erd-theme';

export type ThemePreference = 'system' | 'light' | 'dark';
export type EffectiveTheme = 'light' | 'dark';

type ReadableStorage = Pick<Storage, 'getItem'>;
type WritableStorage = Pick<Storage, 'setItem'>;
type ColorSchemeQuery = Pick<MediaQueryList, 'matches'>;

export function readThemePreference(storage: ReadableStorage): ThemePreference {
  try {
    const stored = storage.getItem(THEME_STORAGE_KEY);
    return stored === 'light' || stored === 'dark' || stored === 'system' ? stored : 'system';
  } catch {
    return 'system';
  }
}

export function storeThemePreference(storage: WritableStorage, preference: ThemePreference): void {
  try {
    storage.setItem(THEME_STORAGE_KEY, preference);
  } catch {
    // Storage may be disabled; the in-memory preference still applies.
  }
}

export function resolveTheme(preference: ThemePreference, query: ColorSchemeQuery): EffectiveTheme {
  return preference === 'system' ? (query.matches ? 'dark' : 'light') : preference;
}

export function applyTheme(theme: EffectiveTheme): void {
  document.documentElement.dataset.theme = theme;
  document.documentElement.style.colorScheme = theme;
}
