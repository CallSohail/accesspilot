import { useCallback, useState } from 'react';
import { api, ApiError } from '../lib/api';
import type { AssistantResponse, Report } from '../lib/types';

/** Build a compact context object from the current report for the assistant. */
function buildContext(report: Report | null): Record<string, unknown> {
  if (!report) return {};
  return {
    report_id: report.report_id,
    document: report.document,
    summary: report.summary,
    findings: report.findings.map((f) => ({
      rule: f.rule,
      severity: f.severity,
      location: f.location,
    })),
  };
}

export function AssistantPanel({
  report,
  providerConfigured,
  backendOffline,
}: {
  report: Report | null;
  providerConfigured: boolean;
  backendOffline: boolean;
}) {
  const [question, setQuestion] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastResponse, setLastResponse] = useState<AssistantResponse | null>(null);

  const ask = useCallback(async () => {
    const q = question.trim();
    if (!q || loading) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.askAssistant(q, buildContext(report));
      setLastResponse(res);
      if (!res.ok) {
        // The backend returns ok:false with an explanatory error string
        // (e.g. how to enable AI when it is not configured).
        setError(res.error ?? 'The assistant returned no answer.');
      }
    } catch (err) {
      setLastResponse(null);
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Could not reach the assistant. Is the backend running?');
      }
    } finally {
      setLoading(false);
    }
  }, [question, loading, report]);

  return (
    <section className="card assistant" aria-labelledby="assistant-heading">
      <h2 id="assistant-heading">Assistant</h2>

      {report ? (
        <p className="muted">
          Context: report <code>{report.report_id}</code> (
          {report.summary.errors} errors, {report.summary.warnings} warnings,{' '}
          {report.summary.info} info)
        </p>
      ) : (
        <p className="muted">No report loaded yet — you can still ask general questions.</p>
      )}

      <div className="assistant__form">
        <label htmlFor="assistant-question" className="visually-hidden">
          Question for the accessibility assistant
        </label>
        <textarea
          id="assistant-question"
          rows={4}
          value={question}
          placeholder="e.g. What should I fix first to improve this document's accessibility?"
          onChange={(e) => setQuestion(e.target.value)}
        />
        <button
          type="button"
          className="button button--primary"
          onClick={ask}
          disabled={loading || question.trim().length === 0}
        >
          {loading ? 'Thinking…' : 'Ask'}
        </button>
      </div>

      <div aria-live="polite" aria-atomic="false">
        {loading && <p className="assistant__loading">The assistant is thinking…</p>}
        {error && (
          <div className="banner banner--error" role="alert">
            {error}
          </div>
        )}
        {lastResponse && lastResponse.ok && (
          <div className="assistant__answer">
            <h3>Answer{lastResponse.model ? ` — via ${lastResponse.model}` : ''}</h3>
            <p>{lastResponse.answer}</p>
          </div>
        )}
      </div>

      {!providerConfigured && !backendOffline && (
        <p className="assistant__hint">
          Tip: AI answers require the backend to be configured with an AI
          provider. When it is not, the assistant returns guidance on how to
          enable it.
        </p>
      )}
    </section>
  );
}
