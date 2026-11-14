import { useCallback, useEffect, useState } from 'react';
import { api, BASE_URL, downloadReport } from './lib/api';
import type { HealthResponse, Report } from './lib/types';
import { AssistantPanel } from './components/AssistantPanel';
import { ReportView } from './components/ReportView';
import { UploadPanel } from './components/UploadPanel';

export default function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [backendOffline, setBackendOffline] = useState(false);

  const [report, setReport] = useState<Report | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .health()
      .then((h) => {
        if (!cancelled) {
          setHealth(h);
          setBackendOffline(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setHealth(null);
          setBackendOffline(true);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleReport = useCallback((r: Report) => {
    setReport(r);
    setDownloadError(null);
  }, []);

  const handleDownload = useCallback(
    async (format: 'json' | 'html') => {
      if (!report) return;
      try {
        await downloadReport(report.report_id, format);
        setDownloadError(null);
      } catch (err) {
        setDownloadError(err instanceof Error ? err.message : 'Download failed');
      }
    },
    [report],
  );

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-header__inner">
          <div>
            <h1>AccessPilot</h1>
            <p className="app-header__tagline">
              Check PDF, DOCX and PPTX documents for accessibility issues.
            </p>
          </div>
          <HealthChip health={health} offline={backendOffline} />
        </div>
      </header>

      <main className="app-main">
        {backendOffline && (
          <div className="banner banner--error" role="alert">
            <strong>Backend not reachable</strong> at {BASE_URL} — is it
            running?
          </div>
        )}

        <div className="app-grid">
          <div className="app-grid__left">
            <UploadPanel onReport={handleReport} />
            {report && (
              <ReportView
                report={report}
                downloadError={downloadError}
                onDownload={handleDownload}
              />
            )}
          </div>
          <aside className="app-grid__right" aria-label="Assistant">
            <AssistantPanel
              report={report}
              providerConfigured={health?.ai_configured ?? false}
              backendOffline={backendOffline}
            />
          </aside>
        </div>
      </main>

      <footer className="app-footer">
        <p>
          AccessPilot · backend expected at <code>{BASE_URL}</code> · reports
          are held in memory by the backend and may expire.
        </p>
      </footer>
    </div>
  );
}

function HealthChip({
  health,
  offline,
}: {
  health: HealthResponse | null;
  offline: boolean;
}) {
  if (offline) {
    return (
      <span className="chip chip--offline" role="status">
        Backend offline
      </span>
    );
  }
  if (!health) {
    return (
      <span className="chip chip--pending" role="status" aria-live="polite">
        Checking backend…
      </span>
    );
  }
  const ai = health.ai_configured
    ? `AI: on${health.ai_model ? ` (${health.ai_model})` : ''}`
    : 'AI: off';
  return (
    <span className="chip chip--online" role="status">
      Backend online · v{health.version} · {ai}
    </span>
  );
}
