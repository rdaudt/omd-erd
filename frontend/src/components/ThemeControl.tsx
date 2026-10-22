import { useEffect, useState } from 'react';
import {
  applyTheme,
  readThemePreference,
  resolveTheme,
  storeThemePreference,
  type ThemePreference,
} from '../theme';

const COLOR_SCHEME_QUERY = '(prefers-color-scheme: dark)';

export function ThemeControl() {
  const [preference, setPreference] = useState<ThemePreference>(() => readThemePreference(localStorage));

  useEffect(() => {
    const query = window.matchMedia(COLOR_SCHEME_QUERY);
    const update = () => applyTheme(resolveTheme(preference, query));
    update();
    if (preference !== 'system') return;
    query.addEventListener('change', update);
    return () => query.removeEventListener('change', update);
  }, [preference]);

  function selectTheme(next: ThemePreference) {
    setPreference(next);
    storeThemePreference(localStorage, next);
  }

  return (
    <label className="theme-control">
      Theme
      <select value={preference} onChange={(event) => selectTheme(event.target.value as ThemePreference)}>
        <option value="system">System</option>
        <option value="light">Light</option>
        <option value="dark">Dark</option>
      </select>
    </label>
  );
}
