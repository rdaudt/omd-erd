import type { GraphResponse } from '../api/types';

export type StatusBannerProps = {
  loading: boolean;
  error: string | null;
  source: GraphResponse['source'] | null;
  warnings: string[];
};

export function StatusBanner({ loading, error, source, warnings }: StatusBannerProps) {
  if (!loading && !error && source !== 'sample' && warnings.length === 0) return null;

  return (
    <div className="status-banner" aria-label="Diagram status">
      {loading && <p role="status">Loading diagram…</p>}
      {error && <p role="alert">{error}</p>}
      {source === 'sample' && <p>Sample data — OpenMetadata unavailable</p>}
      {warnings.map((warning, index) => <p key={`${index}-${warning}`}>{warning}</p>)}
    </div>
  );
}
