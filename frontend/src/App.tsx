import { Navigate, Route, Routes } from "react-router-dom"
import { CasesPage, HealthPage, HistoryPage, ReportPage, SettingsPage, SourcesPage } from "./pages/SecondaryPages"
import { WorkspacePage } from "./pages/WorkspacePage"

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<Navigate to="/" replace />} />
      <Route path="/" element={<WorkspacePage />} />
      <Route path="/history" element={<HistoryPage />} />
      <Route path="/cases" element={<CasesPage />} />
      <Route path="/investigations/:id/report" element={<ReportPage />} />
      <Route path="/sources" element={<SourcesPage />} />
      <Route path="/settings" element={<SettingsPage />} />
      <Route path="/health" element={<HealthPage />} />
    </Routes>
  )
}
