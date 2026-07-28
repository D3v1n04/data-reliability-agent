import { Route, Routes } from "react-router-dom";

import { AppShell } from "./components/AppShell";
import { DashboardPage } from "./pages/DashboardPage";
import { IncidentDetailPage } from "./pages/IncidentDetailPage";
import { IncidentsPage } from "./pages/IncidentsPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { PipelineDetailPage } from "./pages/PipelineDetailPage";
import { PipelinesPage } from "./pages/PipelinesPage";
import { RunDetailPage } from "./pages/RunDetailPage";
import "./App.css";

function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<DashboardPage />} />
        <Route path="pipelines" element={<PipelinesPage />} />
        <Route
          path="pipelines/:pipelineId"
          element={<PipelineDetailPage />}
        />
        <Route path="runs/:runId" element={<RunDetailPage />} />
        <Route path="incidents" element={<IncidentsPage />} />
        <Route
          path="incidents/:incidentId"
          element={<IncidentDetailPage />}
        />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}

export default App;
