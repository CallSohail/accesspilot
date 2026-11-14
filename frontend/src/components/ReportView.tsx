import { useMemo, useState } from 'react';
import type { Finding, Report, Severity, Suggestion } from '../lib/types';

const SEVERITIES: Severity[] = ['error', 'warning', 'info'];

const SOURCE_LABEL: Record<Finding['source'], string> = {
  deterministic: 'Deterministic',
  ai: 'AI suggestion',
  human: 'Needs human review',
};

export function ReportView({
  report,
  downloadError,
  onDownload,
}: {
  report: Report;
  downloadError: string | null;
  onDownload: (format: 'json' | 'html') => void;
}) {
  const [filter, setFilter] = useState<Severity | 'all'>('all');

  const counts = useMemo(() => {
    const c: Record<Severity, number> = { error: 0, warning: 0, info: 0 };
    for (const f of report.findings) c[f.severity] += 1;
    return c;
  }, [report.findings]);

  const visibleFindings = useMemo(() => {
    const filtered =
      filter === 'all'
        ? report.findings
        : report.findings.filter((f) => f.severity === filter);
    return [...filtered].sort((a, b) => {
      const bySev = SEVERITIES.indexOf(a.severity) - SEVERITIES.indexOf(b.severity);
      if (bySev !== 0) return bySev;
      return (a.block_index ?? 0) - (b.block_index ?? 0);
    });
  }, [report.findings, filter]);

  return (
    <div className="report">
      <div className="report__head">
        <div>
          <h2 className="report__title">Report</h2>
          <p className="report__doc">
            <strong>{report.document.filename}</strong>{' '}
            <span className="badge badge--kind">
              {report.document.kind.toUpperCase()}
            </span>
          </p>
          <p className="report__meta">
            <code>report_id: {report.report_id}</code>
          </p>
        </div>
        <div className="report__actions">
          <button type="button" className="button" onClick={() => onDownload('json')}>
            Download JSON
          </button>
          <button type="button" className="button" onClick={() => onDownload('html')}>
            Download HTML
          </button>
        </div>
      </div>

      {downloadError && (
        <p className="banner banner--error" role="alert">
          {downloadError}
        </p>
      )}

      <div className="summary-cards" role="list">
        <SummaryCard label="Errors" value={report.summary.errors} tone="error" role="listitem" />
        <SummaryCard label="Warnings" value={report.summary.warnings} tone="warning" role="listitem" />
        <SummaryCard label="Info" value={report.summary.info} tone="info" role="listitem" />
        <SummaryCard
          label="Blocks"
          value={report.document.num_blocks}
          tone="neutral"
          role="listitem"
        />
      </div>

      <section aria-labelledby="findings-heading">
        <div className="section-head">
          <h3 id="findings-heading">Findings</h3>
          <div className="filter-row" role="group" aria-label="Filter findings by severity">
            <FilterButton
              active={filter === 'all'}
              onClick={() => setFilter('all')}
              count={report.findings.length}
            >
              All
            </FilterButton>
            {SEVERITIES.map((s) => (
              <FilterButton
                key={s}
                active={filter === s}
                tone={s}
                onClick={() => setFilter(s)}
                count={counts[s]}
              >
                {capitalize(s)}
              </FilterButton>
            ))}
          </div>
        </div>

        {visibleFindings.length === 0 ? (
          <p className="muted">No {filter === 'all' ? '' : `${filter} `}findings.</p>
        ) : (
          <ul className="findings">
            {visibleFindings.map((f) => (
              <FindingCard key={f.id} finding={f} />
            ))}
          </ul>
        )}
      </section>

      {report.suggestions.length > 0 && (
        <section aria-labelledby="suggestions-heading">
          <h3 id="suggestions-heading">Before / After suggestions</h3>
          <ul className="suggestions">
            {report.suggestions.map((s, i) => (
              <SuggestionCard key={`${s.finding_id}-${i}`} suggestion={s} />
            ))}
          </ul>
        </section>
      )}

      {report.notes.length > 0 && (
        <section aria-labelledby="notes-heading" className="card">
          <h3 id="notes-heading">Scope &amp; caveats</h3>
          <ul className="notes">
            {report.notes.map((n, i) => (
              <li key={i}>{n}</li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function SummaryCard({
  label,
  value,
  tone,
  role,
}: {
  label: string;
  value: number;
  tone: 'error' | 'warning' | 'info' | 'neutral';
  role?: string;
}) {
  return (
    <div className={`summary-card summary-card--${tone}`} role={role}>
      <span className="summary-card__value">{value}</span>
      <span className="summary-card__label">{label}</span>
    </div>
  );
}

function FilterButton({
  active,
  tone,
  onClick,
  count,
  children,
}: {
  active: boolean;
  tone?: Severity;
  onClick: () => void;
  count: number;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      className={`filter-button ${tone ? `filter-button--${tone}` : ''}`}
      aria-pressed={active}
      onClick={onClick}
    >
      {children}
      <span className="filter-button__count" aria-label={`${count} items`}>
        {count}
      </span>
    </button>
  );
}

function FindingCard({ finding }: { finding: Finding }) {
  return (
    <li className={`finding finding--${finding.severity}`}>
      <div className="finding__head">
        <span className={`badge badge--severity-${finding.severity}`}>
          {capitalize(finding.severity)}
        </span>
        <span className="badge badge--source">{SOURCE_LABEL[finding.source]}</span>
        {finding.wcag_ref && (
          <span className="badge badge--wcag" title="WCAG reference">
            {finding.wcag_ref}
          </span>
        )}
        <span className="finding__location">{finding.location}</span>
      </div>
      <p className="finding__description">
        <strong>{finding.rule}.</strong> {finding.description}
      </p>
      {finding.detail && <p className="finding__detail">{finding.detail}</p>}
      {finding.remediation && (
        <p className="finding__fix">
          <span aria-hidden="true">✓ </span>
          <strong>How to fix:</strong> {finding.remediation}
        </p>
      )}
    </li>
  );
}

function SuggestionCard({ suggestion }: { suggestion: Suggestion }) {
  return (
    <li className="suggestion">
      <div className="suggestion__head">
        <span className="badge badge--source">
          {SOURCE_LABEL[suggestion.source]}
        </span>
        <span className="suggestion__location">{suggestion.location}</span>
      </div>
      <div className="suggestion__cols">
        <div className="suggestion__side suggestion__side--before">
          <h4>Before</h4>
          <pre>{suggestion.before}</pre>
        </div>
        <div className="suggestion__side suggestion__side--after">
          <h4>After</h4>
          <pre>{suggestion.after}</pre>
        </div>
      </div>
      {suggestion.rationale && (
        <p className="suggestion__rationale">
          <strong>Why:</strong> {suggestion.rationale}
        </p>
      )}
    </li>
  );
}

function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}
