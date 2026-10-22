import { describe, expect, it } from 'vitest';
import { readThemePreference, resolveTheme } from './theme';

describe('theme preference', () => {
  it('reads only supported stored preferences', () => {
    expect(readThemePreference({ getItem: () => 'light' })).toBe('light');
    expect(readThemePreference({ getItem: () => 'dark' })).toBe('dark');
    expect(readThemePreference({ getItem: () => 'system' })).toBe('system');
    expect(readThemePreference({ getItem: () => 'invalid' })).toBe('system');
  });

  it('falls back to system when storage is unavailable', () => {
    expect(readThemePreference({ getItem: () => { throw new Error('blocked'); } })).toBe('system');
  });

  it('resolves system preference without overriding explicit choices', () => {
    expect(resolveTheme('system', { matches: true })).toBe('dark');
    expect(resolveTheme('system', { matches: false })).toBe('light');
    expect(resolveTheme('light', { matches: true })).toBe('light');
    expect(resolveTheme('dark', { matches: false })).toBe('dark');
  });
});
