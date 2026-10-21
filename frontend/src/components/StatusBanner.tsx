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
    <section className="status-banner" aria-label="Diagram status">
      {loading && <p className="loading-status" role="status">Loading diagram…</p>}
      {error && <p role="alert">{error}</p>}
      {source === 'sample' && <p className="sample-status" role="status" aria-label="Data source">Sample data — OpenMetadata unavailable</p>}
      {warnings.length > 0 && <div role="status" aria-label="Diagram warnings">{warnings.map((warning, index) => <p key={`${index}-${warning}`}>{warning}</p>)}</div>}
    </section>
  );
}
