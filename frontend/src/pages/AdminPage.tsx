import { useEffect, useState } from "react";
import { api, ApiError } from "../api";
import { Alert, LoadingBlock, Page } from "../components/ui";
import { roleLabel } from "../lib/format";
import type { AdminOrganization, Role, User } from "../types";

export function AdminPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [organizations, setOrganizations] = useState<AdminOrganization[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [savingId, setSavingId] = useState<number | null>(null);

  useEffect(() => {
    Promise.all([api<User[]>("/admin/users"), api<AdminOrganization[]>("/admin/organizations")])
      .then(([userRows, organizationRows]) => {
        setUsers(userRows);
        setOrganizations(organizationRows);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Не удалось загрузить данные"))
      .finally(() => setLoading(false));
  }, []);

  async function changeRole(user: User, role: Role) {
    setSavingId(user.id);
    setError("");
    try {
      const updated = await api<User>(`/admin/users/${user.id}`, {
        method: "PATCH",
        body: JSON.stringify({ role }),
      });
      setUsers((rows) => rows.map((row) => (row.id === updated.id ? updated : row)));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось изменить роль");
    } finally {
      setSavingId(null);
    }
  }

  if (loading) return <LoadingBlock />;

  return (
    <Page title="Администрирование" subtitle="Роли пользователей и список организаций.">
      {error && (
        <div className="mb-4">
          <Alert>{error}</Alert>
        </div>
      )}
      <div className="card overflow-x-auto">
        <table className="w-full min-w-[640px] text-left text-sm">
          <thead className="text-xs uppercase tracking-wide text-zinc-500">
            <tr>
              <th className="px-4 py-3 font-medium">Пользователь</th>
              <th className="px-4 py-3 font-medium">Email</th>
              <th className="px-4 py-3 font-medium">Организации</th>
              <th className="px-4 py-3 font-medium">Роль</th>
            </tr>
          </thead>
          <tbody>
            {users.map((user) => (
              <tr key={user.id} className="border-t border-white/5">
                <td className="px-4 py-3 text-zinc-100">{user.username}</td>
                <td className="px-4 py-3 text-zinc-400">{user.email}</td>
                <td className="px-4 py-3 text-zinc-400">
                  {user.organizations.length === 0 ? "—" : user.organizations.map((item) => item.organization_name).join(", ")}
                </td>
                <td className="px-4 py-3">
                  <select
                    className="input py-1.5"
                    value={user.role}
                    disabled={savingId === user.id}
                    onChange={(event) => changeRole(user, event.target.value as Role)}
                    aria-label={`Роль ${user.username}`}
                  >
                    {(Object.keys(roleLabel) as Role[]).map((role) => (
                      <option key={role} value={role}>
                        {roleLabel[role]}
                      </option>
                    ))}
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <h2 className="mb-3 mt-8 text-sm font-medium uppercase tracking-wide text-zinc-500">Организации</h2>
      {organizations.length === 0 ? (
        <p className="text-sm text-zinc-400">Организаций пока нет.</p>
      ) : (
        <div className="space-y-3">
          {organizations.map((organization) => (
            <div key={organization.id} className="card p-4">
              <div className="flex items-center justify-between gap-3">
                <h3 className="font-medium">{organization.name}</h3>
                <span className="text-xs text-zinc-500">{organization.member_count} в составе</span>
              </div>
              {organization.description && <p className="mt-2 text-sm text-zinc-400">{organization.description}</p>}
            </div>
          ))}
        </div>
      )}
    </Page>
  );
}
