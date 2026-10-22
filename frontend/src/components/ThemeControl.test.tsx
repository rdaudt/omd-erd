import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ThemeControl } from './ThemeControl';

describe('ThemeControl', () => {
  afterEach(() => vi.unstubAllGlobals());
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute('data-theme');
    vi.stubGlobal('matchMedia', vi.fn(() => ({
      matches: true,
      media: '(prefers-color-scheme: dark)',
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })));
  });

  it('applies and remembers an explicit theme choice', async () => {
    const user = userEvent.setup();
    render(<ThemeControl />);

    const control = screen.getByRole('combobox', { name: 'Theme' });
    expect(control).toHaveValue('system');
    expect(document.documentElement.dataset.theme).toBe('dark');

    await user.selectOptions(control, 'light');

    expect(document.documentElement.dataset.theme).toBe('light');
    expect(localStorage.getItem('omd-erd-theme')).toBe('light');
  });
});
