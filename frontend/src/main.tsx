import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './styles.css';

// Note for developers: AccessPilot expects the backend on :8000
// (see src/lib/api.ts and vite.config.ts).
console.info('AccessPilot frontend — backend expected at http://localhost:8000');

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
