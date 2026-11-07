import { Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { RequireAuth } from "./components/RequireAuth";
import { ContestFormPage } from "./pages/ContestFormPage";
import { ContestPage } from "./pages/ContestPage";
import { ContestReportsPage } from "./pages/ContestReportsPage";
import { ContestsPage } from "./pages/ContestsPage";
import { AdminPage } from "./pages/AdminPage";
import { ArenaJoinPage, ArenaLobbyPage, ArenaRoomPage } from "./pages/ArenaPage";
import { HomePage } from "./pages/HomePage";
import { LoginPage } from "./pages/LoginPage";
import { OrganizationPage } from "./pages/OrganizationPage";
import { OrganizationProblemPage } from "./pages/OrganizationProblemPage";
import { ProblemsPage } from "./pages/ProblemsPage";
import { ProductionPage } from "./pages/ProductionPage";
import { RegisterOrganizationPage } from "./pages/RegisterOrganizationPage";
import { RegisterPage } from "./pages/RegisterPage";
import { SolvePage } from "./pages/SolvePage";
import { FairPlayPage, FairPlayReportPage } from "./pages/FairPlayPage";
import { TeamCreatePage, TeamsPage } from "./pages/TeamsPage";
import { TeamPage } from "./pages/TeamPage";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/register-organization" element={<RegisterOrganizationPage />} />
        <Route
          path="/admin"
          element={
            <RequireAuth role="admin">
              <AdminPage />
            </RequireAuth>
          }
        />
        <Route path="/problems" element={<ProblemsPage />} />
        <Route path="/problems/:problemId" element={<SolvePage />} />
        <Route path="/production" element={<ProductionPage />} />
        <Route path="/teams" element={<TeamsPage />} />
        <Route
          path="/teams/new"
          element={
            <RequireAuth>
              <TeamCreatePage />
            </RequireAuth>
          }
        />
        <Route path="/teams/:teamId" element={<TeamPage />} />
        <Route
          path="/organization"
          element={
            <RequireAuth>
              <OrganizationPage />
            </RequireAuth>
          }
        />
        <Route
          path="/organization/:orgId"
          element={
            <RequireAuth>
              <OrganizationPage />
            </RequireAuth>
          }
        />
        <Route
          path="/organization/:orgId/problems/new"
          element={
            <RequireAuth role="organizer">
              <OrganizationProblemPage />
            </RequireAuth>
          }
        />
        <Route
          path="/organization/:orgId/problems/:problemId"
          element={
            <RequireAuth role="organizer">
              <OrganizationProblemPage />
            </RequireAuth>
          }
        />
        <Route path="/contests" element={<ContestsPage />} />
        <Route
          path="/play"
          element={
            <RequireAuth>
              <ArenaLobbyPage />
            </RequireAuth>
          }
        />
        <Route
          path="/play/join/:code"
          element={
            <RequireAuth>
              <ArenaJoinPage />
            </RequireAuth>
          }
        />
        <Route
          path="/play/:matchId"
          element={
            <RequireAuth>
              <ArenaRoomPage />
            </RequireAuth>
          }
        />
        <Route
          path="/contests/new"
          element={
            <RequireAuth role="organizer">
              <ContestFormPage />
            </RequireAuth>
          }
        />
        <Route path="/contests/:contestId" element={<ContestPage />} />
        <Route
          path="/contests/:contestId/reports"
          element={
            <RequireAuth role="organizer">
              <ContestReportsPage />
            </RequireAuth>
          }
        />
        <Route
          path="/contests/:contestId/fairplay"
          element={
            <RequireAuth role="organizer">
              <FairPlayPage />
            </RequireAuth>
          }
        />
        <Route
          path="/contests/:contestId/fairplay/:reportId"
          element={
            <RequireAuth role="organizer">
              <FairPlayReportPage />
            </RequireAuth>
          }
        />
        <Route
          path="/contests/:contestId/edit"
          element={
            <RequireAuth role="organizer">
              <ContestFormPage />
            </RequireAuth>
          }
        />
        <Route path="/contests/:contestId/problems/:problemId" element={<SolvePage />} />
      </Route>
    </Routes>
  );
}
