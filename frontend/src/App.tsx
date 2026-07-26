import { Navigate, Route, Routes } from 'react-router-dom';
import { AppShell } from './components/layout/AppShell';
import { LiveMonitorPage } from './pages/LiveMonitorPage';
import { CorrelationsPage } from './pages/CorrelationsPage';
import { HistoricalEventsPage } from './pages/HistoricalEventsPage';
import { FeedbackLogPage } from './pages/FeedbackLogPage';

export function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<LiveMonitorPage />} />
        <Route path="/correlations" element={<CorrelationsPage />} />
        <Route path="/events" element={<HistoricalEventsPage />} />
        <Route path="/feedback" element={<FeedbackLogPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppShell>
  );
}
