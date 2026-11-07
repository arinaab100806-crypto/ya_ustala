import type { ReactElement } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../auth";
import { LoadingBlock, Page } from "./ui";

export function RequireAuth({ role, children }: { role?: "organizer" | "admin"; children: ReactElement }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) {
    return (
      <div className="mx-auto max-w-6xl px-4">
        <LoadingBlock />
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  const allowed = !role || (role === "admin" ? user.role === "admin" : user.can_organize);
  if (!allowed) {
    return (
      <Page
        title="Недостаточно прав"
        subtitle={role === "admin" ? "Раздел доступен только администратору." : "Создавать соревнования может владелец организации, назначенный организатор или администратор."}
      >
        <p className="text-sm text-zinc-400">
          {role === "admin" ? "Войдите под учётной записью администратора." : "Зарегистрируйте организацию или попросите администратора назначить роль."}
        </p>
      </Page>
    );
  }
  return children;
}
