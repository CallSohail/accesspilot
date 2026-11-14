import { useCallback, useRef, useState } from 'react';
import { api, ApiError } from '../lib/api';
import type { Report } from '../lib/types';

const ACCEPTED = ['.pdf', '.docx', '.pptx'];

export function UploadPanel({ onReport }: { onReport: (r: Report) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const acceptFile = useCallback((candidate: File) => {
    const ext = candidate.name.slice(candidate.name.lastIndexOf('.')).toLowerCase();
    if (!ACCEPTED.includes(ext)) {
      setError(
        `Unsupported file type "${ext}". Accepted: .pdf, .docx, .pptx.`,
      );
      return;
    }
    if (candidate.size === 0) {
      setError('That file is empty.');
      return;
    }
    setError(null);
    setFile(candidate);
  }, []);

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const f = e.dataTransfer.files?.[0];
      if (f) acceptFile(f);
    },
    [acceptFile],
  );

  const submit = useCallback(async () => {
    if (!file || loading) return;
    setLoading(true);
    setError(null);
    try {
      const report = await api.analyze(file);
      onReport(report);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Unexpected error while analyzing the file.');
      }
    } finally {
      setLoading(false);
    }
  }, [file, loading, onReport]);

  return (
    <section className="card" aria-labelledby="upload-heading">
      <h2 id="upload-heading">Analyze a document</h2>

      <div
        className={`dropzone ${dragOver ? 'dropzone--active' : ''}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
      >
        <input
          ref={inputRef}
          id="file-input"
          type="file"
          accept={ACCEPTED.join(',')}
          className="visually-hidden"
          aria-label="Choose a document to analyze (.pdf, .docx or .pptx)"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) acceptFile(f);
            e.target.value = '';
          }}
        />
        <p>
          Drag &amp; drop a file here, or{' '}
          <button
            type="button"
            className="link-button"
            onClick={() => inputRef.current?.click()}
          >
            browse
          </button>
        </p>
        <p className="dropzone__hint">Accepted: .pdf, .docx, .pptx</p>
      </div>

      <div className="upload-row">
        <span className="upload-filename">
          {file ? (
            <>
              <strong>{file.name}</strong> ({formatBytes(file.size)})
            </>
          ) : (
            'No file selected'
          )}
        </span>
        <button
          type="button"
          className="button button--primary"
          disabled={!file || loading}
          onClick={submit}
        >
          {loading ? 'Analyzing…' : 'Analyze'}
        </button>
      </div>

      <div aria-live="polite" aria-atomic="true">
        {loading && (
          <p className="upload-status">
            Analyzing <strong>{file?.name}</strong>…
          </p>
        )}
        {error && (
          <p className="banner banner--error" role="alert">
            {error}
          </p>
        )}
      </div>
    </section>
  );
}

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}
