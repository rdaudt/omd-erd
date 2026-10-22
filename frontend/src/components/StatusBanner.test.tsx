import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { StatusBanner } from './StatusBanner';

describe('StatusBanner', () => {
  it('renders cross-schema notices as neutral status content', () => {
    render(
      <StatusBanner
        loading={false}
        error={null}
        source="live"
        notices={['2 cross-schema relationships are not shown.']}
        warnings={[]}
      />,
    );

    expect(screen.getByRole('status', { name: 'Diagram notices' })).toHaveTextContent(
      '2 cross-schema relationships are not shown.',
    );
    expect(screen.queryByRole('status', { name: 'Diagram warnings' })).not.toBeInTheDocument();
  });
});
