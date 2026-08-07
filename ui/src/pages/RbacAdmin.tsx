/**
 * RBAC Admin Page — Role-Based Access Control management UI.
 *
 * Wires to all 9 endpoints exposed by api/rbac.py (prefix /api/v1/auth):
 *   GET    /roles                         — list roles (paginated)
 *   POST   /roles                         — create role
 *   PUT    /roles/{role_id}               — update role (name/description/permissions)
 *   DELETE /roles/{role_id}               — delete role
 *   GET    /permissions                   — list permissions (paginated)
 *   POST   /permissions                   — create permission
 *   GET    /users/{user_id}/roles         — get user's roles
 *   POST   /users/{user_id}/roles         — assign roles to user (replaces existing)
 *   DELETE /users/{user_id}/roles/{role_id} — remove single role from user
 *
 * NOTE: The brief mentioned "10 endpoints" but api/rbac.py only exposes 9
 * HTTP endpoints — the 10th match in the audit grep was a docstring example
 * inside require_permission(). See worklog TASK-1 for the deviation note.
 *
 * Ref: TASK-1
 */

import { motion } from "framer-motion";
import {
  AlertTriangle,
  KeyRound,
  Loader2,
  Pencil,
  Plus,
  Search,
  Shield,
  ShieldCheck,
  Trash2,
  UserCog,
  Users,
} from "lucide-react";
import { type ReactNode, useCallback, useEffect, useMemo, useState } from "react";
import { Badge, Button, Card, EmptyState, Modal, Tabs } from "../components/ui";
import { useNotify } from "../context/NotificationContext";
import { API_BASE_URL } from "../lib/api-config";
import { getAuthToken } from "../lib/tokenStorage";

// ---------------------------------------------------------------------------
// Types — mirror api/rbac.py Pydantic schemas
// ---------------------------------------------------------------------------

interface Permission {
  id: string;
  resource: string;
  action: string;
  description: string | null;
  created_at: string | null;
}

interface PermissionListResponse {
  permissions: Permission[];
  total: number;
  page: number;
  page_size: number;
}

interface Role {
  id: string;
  name: string;
  description: string | null;
  is_system: boolean;
  permission_ids: string[];
  created_at: string | null;
  updated_at: string | null;
}

interface RoleListResponse {
  roles: Role[];
  total: number;
  page: number;
  page_size: number;
}

interface UserRoleResponse {
  user_id: string;
  roles: Role[];
}

type TabId = "roles" | "permissions" | "assignments";

// ---------------------------------------------------------------------------
// Fetch helpers
// ---------------------------------------------------------------------------

function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const token = getAuthToken();
  return { ...(token ? { Authorization: `Bearer ${token}` } : {}), ...extra };
}

async function rbacFetch<T>(path: string, init?: RequestInit): Promise<T> {
  // Merge our auth+content-type headers with any caller-provided headers.
  // Caller headers may be Headers | string[] | Record — normalize to a plain
  // record by stringifying known keys we care about; we only ever pass
  // Record<string, string> from this module so a narrow cast is safe.
  const callerHeaders = init?.headers;
  const mergedHeaders: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (callerHeaders instanceof Headers) {
    callerHeaders.forEach((value, key) => {
      mergedHeaders[key] = value;
    });
  } else if (Array.isArray(callerHeaders)) {
    for (const [key, value] of callerHeaders) {
      mergedHeaders[key] = value;
    }
  } else if (callerHeaders && typeof callerHeaders === "object") {
    for (const [key, value] of Object.entries(callerHeaders)) {
      mergedHeaders[key] = value;
    }
  }
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: authHeaders(mergedHeaders),
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (body?.detail)
        detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* ignore — non-JSON error body */
    }
    throw new Error(detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

// ---------------------------------------------------------------------------
// Role modal — create/edit with permission multi-select
// ---------------------------------------------------------------------------

interface RoleModalProps {
  readonly open: boolean;
  readonly onClose: () => void;
  readonly onSaved: () => void;
  readonly permissions: Permission[];
  readonly editingRole: Role | null;
}

function RoleModal({ open, onClose, onSaved, permissions, editingRole }: RoleModalProps) {
  const { notify } = useNotify();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [selectedPermIds, setSelectedPermIds] = useState<Set<string>>(new Set());
  const [saving, setSaving] = useState(false);
  const [permFilter, setPermFilter] = useState("");

  // Sync form state whenever the modal opens or the editing target changes.
  useEffect(() => {
    if (!open) return;
    setName(editingRole?.name ?? "");
    setDescription(editingRole?.description ?? "");
    setSelectedPermIds(new Set(editingRole?.permission_ids ?? []));
    setPermFilter("");
  }, [open, editingRole]);

  const togglePermission = (id: string) => {
    setSelectedPermIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const filteredPermissions = useMemo(() => {
    const q = permFilter.trim().toLowerCase();
    if (!q) return permissions;
    return permissions.filter(
      (p) =>
        p.resource.toLowerCase().includes(q) ||
        p.action.toLowerCase().includes(q) ||
        (p.description ?? "").toLowerCase().includes(q),
    );
  }, [permissions, permFilter]);

  const handleSave = async () => {
    const trimmedName = name.trim();
    if (!trimmedName) {
      notify("warning", "Role name is required");
      return;
    }
    setSaving(true);
    try {
      const payload = {
        name: trimmedName,
        description: description.trim() || null,
        permission_ids: Array.from(selectedPermIds),
      };
      if (editingRole) {
        await rbacFetch(`/api/v1/auth/roles/${editingRole.id}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
        notify("success", `Role "${trimmedName}" updated`);
      } else {
        await rbacFetch("/api/v1/auth/roles", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        notify("success", `Role "${trimmedName}" created`);
      }
      onSaved();
      onClose();
    } catch (err) {
      notify("error", `Failed to save role: ${err instanceof Error ? err.message : "unknown"}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={editingRole ? "Edit Role" : "Create Role"}
      subtitle={
        editingRole ? `Updating ${editingRole.name}` : "Define a new role and assign permissions"
      }
      size="lg"
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button onClick={handleSave} loading={saving} disabled={!name.trim()}>
            {editingRole ? "Update Role" : "Create Role"}
          </Button>
        </div>
      }
    >
      <div className="space-y-4">
        <div>
          <label
            htmlFor="rbac-role-name"
            className="block text-sm font-medium text-[var(--text-primary)] mb-1"
          >
            Name
          </label>
          <input
            id="rbac-role-name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. engineer, operator, viewer"
            pattern="^[a-zA-Z0-9_-]+$"
            title="Letters, numbers, underscores, hyphens only"
            className="w-full px-3 py-2 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-[var(--text-primary)]"
          />
          <p className="text-xs text-[var(--text-muted)] mt-1">
            Letters, numbers, underscores and hyphens only (max 64 chars).
          </p>
        </div>

        <div>
          <label
            htmlFor="rbac-role-description"
            className="block text-sm font-medium text-[var(--text-primary)] mb-1"
          >
            Description
          </label>
          <textarea
            id="rbac-role-description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={2}
            placeholder="What can users with this role do?"
            className="w-full px-3 py-2 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-[var(--text-primary)]"
          />
        </div>

        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="block text-sm font-medium text-[var(--text-primary)]">
              <span>Permissions</span>
              <span className="ml-2 text-xs text-[var(--text-muted)]">
                {selectedPermIds.size} selected
              </span>
            </span>
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[var(--text-muted)]" />
              <input
                type="text"
                value={permFilter}
                onChange={(e) => setPermFilter(e.target.value)}
                placeholder="Filter permissions..."
                className="pl-8 pr-3 py-1.5 text-xs rounded-md border border-[var(--border-primary)] bg-[var(--bg-primary)] text-[var(--text-primary)] w-56"
              />
            </div>
          </div>
          <div className="max-h-64 overflow-y-auto rounded-lg border border-[var(--border-primary)] divide-y divide-[var(--border-primary)]">
            {filteredPermissions.length === 0 ? (
              <div className="p-4 text-center text-sm text-[var(--text-muted)]">
                No permissions available. Create permissions in the Permissions tab first.
              </div>
            ) : (
              filteredPermissions.map((p) => {
                const checked = selectedPermIds.has(p.id);
                return (
                  <label
                    key={p.id}
                    className={`flex items-center gap-3 px-3 py-2 cursor-pointer hover:bg-[var(--bg-elevated)] transition-colors ${
                      checked ? "bg-brand-500/5" : ""
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => togglePermission(p.id)}
                      className="w-4 h-4 rounded"
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs text-[var(--text-primary)]">
                          {p.resource}:{p.action}
                        </span>
                      </div>
                      {p.description && (
                        <p className="text-xs text-[var(--text-muted)] truncate">{p.description}</p>
                      )}
                    </div>
                  </label>
                );
              })
            )}
          </div>
        </div>
      </div>
    </Modal>
  );
}

// ---------------------------------------------------------------------------
// Permission modal — create new permission
// ---------------------------------------------------------------------------

interface PermissionModalProps {
  readonly open: boolean;
  readonly onClose: () => void;
  readonly onSaved: () => void;
}

function PermissionModal({ open, onClose, onSaved }: PermissionModalProps) {
  const { notify } = useNotify();
  const [resource, setResource] = useState("");
  const [action, setAction] = useState("");
  const [description, setDescription] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    setResource("");
    setAction("");
    setDescription("");
  }, [open]);

  const handleSave = async () => {
    const r = resource.trim();
    const a = action.trim();
    if (!r || !a) {
      notify("warning", "Resource and action are required");
      return;
    }
    setSaving(true);
    try {
      await rbacFetch("/api/v1/auth/permissions", {
        method: "POST",
        body: JSON.stringify({
          resource: r,
          action: a,
          description: description.trim() || null,
        }),
      });
      notify("success", `Permission ${r}:${a} created`);
      onSaved();
      onClose();
    } catch (err) {
      notify(
        "error",
        `Failed to create permission: ${err instanceof Error ? err.message : "unknown"}`,
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Create Permission"
      subtitle="Define a new resource:action pair"
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button
            onClick={handleSave}
            loading={saving}
            disabled={!resource.trim() || !action.trim()}
          >
            Create Permission
          </Button>
        </div>
      }
    >
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label
              htmlFor="perm-resource"
              className="block text-sm font-medium text-[var(--text-primary)] mb-1"
            >
              Resource
            </label>
            <input
              id="perm-resource"
              type="text"
              value={resource}
              onChange={(e) => setResource(e.target.value)}
              placeholder="e.g. projects, studies, equipment"
              className="w-full px-3 py-2 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-[var(--text-primary)]"
            />
          </div>
          <div>
            <label
              htmlFor="perm-action"
              className="block text-sm font-medium text-[var(--text-primary)] mb-1"
            >
              Action
            </label>
            <input
              id="perm-action"
              type="text"
              value={action}
              onChange={(e) => setAction(e.target.value)}
              placeholder="e.g. read, create, delete"
              className="w-full px-3 py-2 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-[var(--text-primary)]"
            />
          </div>
        </div>
        <div>
          <label
            htmlFor="perm-description"
            className="block text-sm font-medium text-[var(--text-primary)] mb-1"
          >
            Description (optional)
          </label>
          <input
            id="perm-description"
            type="text"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="What does this permission grant?"
            className="w-full px-3 py-2 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-[var(--text-primary)]"
          />
        </div>
      </div>
    </Modal>
  );
}

// ---------------------------------------------------------------------------
// Roles tab
// ---------------------------------------------------------------------------

interface RolesTabProps {
  readonly roles: Role[];
  readonly permissions: Permission[];
  readonly loading: boolean;
  readonly error: string | null;
  readonly onReload: () => void;
  readonly onEdit: (role: Role) => void;
  readonly onCreate: () => void;
  readonly onDeleted: () => void;
}

function RolesTab({
  roles,
  permissions,
  loading,
  error,
  onReload,
  onEdit,
  onCreate,
  onDeleted,
}: RolesTabProps) {
  const { notify } = useNotify();
  const [search, setSearch] = useState("");
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<Role | null>(null);

  const permLookup = useMemo(() => {
    const m = new Map<string, Permission>();
    for (const p of permissions) m.set(p.id, p);
    return m;
  }, [permissions]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return roles;
    return roles.filter(
      (r) => r.name.toLowerCase().includes(q) || (r.description ?? "").toLowerCase().includes(q),
    );
  }, [roles, search]);

  const handleDelete = async (role: Role) => {
    setDeletingId(role.id);
    try {
      await rbacFetch(`/api/v1/auth/roles/${role.id}`, { method: "DELETE" });
      notify("success", `Role "${role.name}" deleted`);
      onDeleted();
      setConfirmDelete(null);
    } catch (err) {
      notify("error", `Failed to delete role: ${err instanceof Error ? err.message : "unknown"}`);
    } finally {
      setDeletingId(null);
    }
  };

  let content: ReactNode;
  if (loading) {
    content = (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-brand-500" />
      </div>
    );
  } else if (error) {
    content = (
      <Card>
        <EmptyState
          icon={<AlertTriangle className="w-10 h-10" />}
          title="Failed to load roles"
          description={error}
          action={<Button onClick={onReload}>Retry</Button>}
        />
      </Card>
    );
  } else if (filtered.length === 0) {
    content = (
      <Card>
        <EmptyState
          icon={<Shield className="w-10 h-10" />}
          title={search ? "No roles match your filter" : "No roles yet"}
          description={
            search
              ? "Try a different search term."
              : "Create your first role to start managing permissions."
          }
          action={
            !search ? (
              <Button onClick={onCreate}>
                <Plus className="w-4 h-4" /> New Role
              </Button>
            ) : undefined
          }
        />
      </Card>
    );
  } else {
    content = (
      <Card padding="none">
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left text-[var(--text-secondary)]">
            <thead className="text-[11px] uppercase tracking-wider text-[var(--text-muted)] border-b border-[var(--border-primary)]">
              <tr>
                <th className="py-3 px-4">Name</th>
                <th className="py-3 px-4">Description</th>
                <th className="py-3 px-4">Permissions</th>
                <th className="py-3 px-4">Type</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border-primary)]">
              {filtered.map((role) => (
                <tr key={role.id} className="hover:bg-[var(--bg-elevated)] transition-colors">
                  <td className="py-3 px-4 font-medium text-[var(--text-primary)]">
                    <div className="flex items-center gap-2">
                      <ShieldCheck className="w-4 h-4 text-brand-400 shrink-0" />
                      {role.name}
                    </div>
                  </td>
                  <td className="py-3 px-4 text-[var(--text-muted)] max-w-xs">
                    {role.description || <span className="italic">—</span>}
                  </td>
                  <td className="py-3 px-4">
                    <div className="flex flex-wrap gap-1 max-w-md">
                      {role.permission_ids.length === 0 ? (
                        <span className="text-xs text-[var(--text-muted)] italic">
                          No permissions
                        </span>
                      ) : (
                        role.permission_ids.slice(0, 4).map((pid) => {
                          const p = permLookup.get(pid);
                          return (
                            <Badge key={pid} variant="info" size="sm">
                              {p ? `${p.resource}:${p.action}` : "unknown"}
                            </Badge>
                          );
                        })
                      )}
                      {role.permission_ids.length > 4 && (
                        <Badge variant="neutral" size="sm">
                          +{role.permission_ids.length - 4} more
                        </Badge>
                      )}
                    </div>
                  </td>
                  <td className="py-3 px-4">
                    {role.is_system ? (
                      <Badge variant="warning" size="sm">
                        system
                      </Badge>
                    ) : (
                      <Badge variant="default" size="sm">
                        custom
                      </Badge>
                    )}
                  </td>
                  <td className="py-3 px-4 text-right">
                    <div className="flex justify-end gap-1">
                      <button
                        type="button"
                        onClick={() => onEdit(role)}
                        className="p-1.5 rounded-md text-[var(--text-muted)] hover:text-brand-400 hover:bg-brand-500/10 transition-colors"
                        title="Edit role"
                        aria-label={`Edit role ${role.name}`}
                      >
                        <Pencil className="w-4 h-4" />
                      </button>
                      <button
                        type="button"
                        onClick={() => setConfirmDelete(role)}
                        disabled={role.is_system || deletingId === role.id}
                        className="p-1.5 rounded-md text-[var(--text-muted)] hover:text-red-400 hover:bg-red-500/10 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                        title={role.is_system ? "System roles cannot be deleted" : "Delete role"}
                        aria-label={`Delete role ${role.name}`}
                      >
                        {deletingId === role.id ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <Trash2 className="w-4 h-4" />
                        )}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-muted)]" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search roles by name or description..."
            className="w-full pl-10 pr-4 py-2.5 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:ring-2 focus:ring-brand-500/50"
          />
        </div>
        <Button onClick={onCreate}>
          <Plus className="w-4 h-4" /> New Role
        </Button>
      </div>
      {content}

      <Modal
        open={confirmDelete !== null}
        onClose={() => setConfirmDelete(null)}
        title="Delete Role"
        size="sm"
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setConfirmDelete(null)}>
              Cancel
            </Button>
            <Button
              variant="danger"
              loading={deletingId === confirmDelete?.id}
              onClick={() => confirmDelete && handleDelete(confirmDelete)}
            >
              Delete Role
            </Button>
          </div>
        }
      >
        <p className="text-sm text-[var(--text-secondary)]">
          Are you sure you want to delete the role{" "}
          <span className="font-semibold text-[var(--text-primary)]">{confirmDelete?.name}</span>?
          Users assigned to this role will lose the associated permissions immediately.
        </p>
      </Modal>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Permissions tab
// ---------------------------------------------------------------------------

interface PermissionsTabProps {
  readonly permissions: Permission[];
  readonly loading: boolean;
  readonly error: string | null;
  readonly onReload: () => void;
  readonly onCreate: () => void;
}

function PermissionsTab({ permissions, loading, error, onReload, onCreate }: PermissionsTabProps) {
  const [search, setSearch] = useState("");

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return permissions;
    return permissions.filter(
      (p) =>
        p.resource.toLowerCase().includes(q) ||
        p.action.toLowerCase().includes(q) ||
        (p.description ?? "").toLowerCase().includes(q),
    );
  }, [permissions, search]);

  // Group permissions by resource for a cleaner matrix view.
  const grouped = useMemo(() => {
    const m = new Map<string, Permission[]>();
    for (const p of filtered) {
      const arr = m.get(p.resource) ?? [];
      arr.push(p);
      m.set(p.resource, arr);
    }
    return Array.from(m.entries()).sort((a, b) => a[0].localeCompare(b[0]));
  }, [filtered]);

  let content: ReactNode;
  if (loading) {
    content = (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-brand-500" />
      </div>
    );
  } else if (error) {
    content = (
      <Card>
        <EmptyState
          icon={<AlertTriangle className="w-10 h-10" />}
          title="Failed to load permissions"
          description={error}
          action={<Button onClick={onReload}>Retry</Button>}
        />
      </Card>
    );
  } else if (filtered.length === 0) {
    content = (
      <Card>
        <EmptyState
          icon={<KeyRound className="w-10 h-10" />}
          title={search ? "No permissions match your filter" : "No permissions yet"}
          description={
            search
              ? "Try a different search term."
              : "Create your first permission (resource:action pair) to start assigning them to roles."
          }
          action={
            !search ? (
              <Button onClick={onCreate}>
                <Plus className="w-4 h-4" /> New Permission
              </Button>
            ) : undefined
          }
        />
      </Card>
    );
  } else {
    content = (
      <div className="space-y-3">
        {grouped.map(([resource, perms]) => (
          <Card key={resource} padding="md">
            <div className="flex items-center gap-2 mb-3">
              <KeyRound className="w-4 h-4 text-brand-400" />
              <h3 className="font-mono text-sm font-semibold text-[var(--text-primary)]">
                {resource}
              </h3>
              <Badge variant="neutral" size="sm">
                {perms.length}
              </Badge>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
              {perms.map((p) => (
                <div
                  key={p.id}
                  className="flex items-start gap-2 p-2 rounded-md bg-[var(--bg-elevated)] border border-[var(--border-primary)]"
                >
                  <Badge variant="info" size="sm" className="mt-0.5">
                    {p.action}
                  </Badge>
                  <div className="min-w-0 flex-1">
                    {p.description ? (
                      <p className="text-xs text-[var(--text-secondary)] truncate">
                        {p.description}
                      </p>
                    ) : (
                      <p className="text-xs text-[var(--text-muted)] italic">No description</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-muted)]" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search permissions by resource, action, or description..."
            className="w-full pl-10 pr-4 py-2.5 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:ring-2 focus:ring-brand-500/50"
          />
        </div>
        <Button onClick={onCreate}>
          <Plus className="w-4 h-4" /> New Permission
        </Button>
      </div>
      {content}
    </div>
  );
}

// ---------------------------------------------------------------------------
// User-role assignments tab
// ---------------------------------------------------------------------------

interface AssignmentsTabProps {
  readonly roles: Role[];
}

function AssignmentsTab({ roles }: AssignmentsTabProps) {
  const { notify } = useNotify();
  const [userId, setUserId] = useState("");
  const [assignment, setAssignment] = useState<UserRoleResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedRoleIds, setSelectedRoleIds] = useState<Set<string>>(new Set());
  const [saving, setSaving] = useState(false);
  const [removingRoleId, setRemovingRoleId] = useState<string | null>(null);

  const fetchUserRoles = useCallback(async (id: string) => {
    if (!id.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const data = await rbacFetch<UserRoleResponse>(
        `/api/v1/auth/users/${encodeURIComponent(id.trim())}/roles`,
      );
      setAssignment(data);
      setSelectedRoleIds(new Set(data.roles.map((r) => r.id)));
    } catch (err) {
      setAssignment(null);
      setError(err instanceof Error ? err.message : "unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  const handleAssign = async () => {
    if (!assignment || selectedRoleIds.size === 0) {
      notify("warning", "Select at least one role to assign");
      return;
    }
    setSaving(true);
    try {
      const data = await rbacFetch<UserRoleResponse>(
        `/api/v1/auth/users/${encodeURIComponent(assignment.user_id)}/roles`,
        {
          method: "POST",
          body: JSON.stringify({ role_ids: Array.from(selectedRoleIds) }),
        },
      );
      setAssignment(data);
      setSelectedRoleIds(new Set(data.roles.map((r) => r.id)));
      notify("success", `Roles updated for user ${assignment.user_id}`);
    } catch (err) {
      notify("error", `Failed to assign roles: ${err instanceof Error ? err.message : "unknown"}`);
    } finally {
      setSaving(false);
    }
  };

  const handleRemoveRole = async (roleId: string) => {
    if (!assignment) return;
    setRemovingRoleId(roleId);
    try {
      await rbacFetch(
        `/api/v1/auth/users/${encodeURIComponent(assignment.user_id)}/roles/${encodeURIComponent(roleId)}`,
        { method: "DELETE" },
      );
      notify("success", "Role removed from user");
      await fetchUserRoles(assignment.user_id);
    } catch (err) {
      notify("error", `Failed to remove role: ${err instanceof Error ? err.message : "unknown"}`);
    } finally {
      setRemovingRoleId(null);
    }
  };

  const toggleRole = (id: string) => {
    setSelectedRoleIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <div className="space-y-4">
      <Card padding="md">
        <div className="flex items-end gap-3">
          <div className="flex-1">
            <label
              htmlFor="rbac-user-id"
              className="block text-sm font-medium text-[var(--text-primary)] mb-1"
            >
              User ID
            </label>
            <input
              id="rbac-user-id"
              type="text"
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              placeholder="Paste a user UUID to look up their role assignments"
              className="w-full px-3 py-2 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-[var(--text-primary)] font-mono text-sm"
              onKeyDown={(e) => {
                if (e.key === "Enter") fetchUserRoles(userId);
              }}
            />
          </div>
          <Button
            onClick={() => fetchUserRoles(userId)}
            loading={loading}
            disabled={!userId.trim()}
          >
            <Search className="w-4 h-4" /> Lookup
          </Button>
        </div>
      </Card>

      {!assignment && !loading && !error && (
        <Card>
          <EmptyState
            icon={<Users className="w-10 h-10" />}
            title="No user selected"
            description="Enter a user ID above and click Lookup to view and manage their role assignments."
          />
        </Card>
      )}

      {error && (
        <Card>
          <EmptyState
            icon={<AlertTriangle className="w-10 h-10" />}
            title="Lookup failed"
            description={error}
          />
        </Card>
      )}

      {loading && (
        <Card>
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-brand-500" />
          </div>
        </Card>
      )}

      {assignment && !loading && (
        <>
          <Card padding="md">
            <div className="flex items-center gap-2 mb-3">
              <UserCog className="w-4 h-4 text-brand-400" />
              <h3 className="text-sm font-semibold text-[var(--text-primary)]">
                Current roles for{" "}
                <span className="font-mono text-[var(--text-secondary)]">{assignment.user_id}</span>
              </h3>
              <Badge variant="brand" size="sm">
                {assignment.roles.length}
              </Badge>
            </div>
            {assignment.roles.length === 0 ? (
              <p className="text-sm text-[var(--text-muted)] italic">
                This user has no role assignments yet.
              </p>
            ) : (
              <div className="space-y-2">
                {assignment.roles.map((role) => (
                  <div
                    key={role.id}
                    className="flex items-center justify-between p-2 rounded-md bg-[var(--bg-elevated)] border border-[var(--border-primary)]"
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <ShieldCheck className="w-4 h-4 text-brand-400 shrink-0" />
                      <div className="min-w-0">
                        <div className="text-sm font-medium text-[var(--text-primary)]">
                          {role.name}
                        </div>
                        <div className="text-xs text-[var(--text-muted)] truncate">
                          {role.permission_ids.length} permissions
                          {role.description ? ` · ${role.description}` : ""}
                        </div>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleRemoveRole(role.id)}
                      disabled={removingRoleId === role.id}
                      className="p-1.5 rounded-md text-[var(--text-muted)] hover:text-red-400 hover:bg-red-500/10 transition-colors disabled:opacity-50"
                      title="Remove role from user"
                      aria-label={`Remove role ${role.name} from user`}
                    >
                      {removingRoleId === role.id ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <Trash2 className="w-4 h-4" />
                      )}
                    </button>
                  </div>
                ))}
              </div>
            )}
          </Card>

          <Card padding="md">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-[var(--text-primary)]">
                Update role assignments
              </h3>
              <Button onClick={handleAssign} loading={saving} size="sm">
                Save Assignments
              </Button>
            </div>
            <p className="text-xs text-[var(--text-muted)] mb-3">
              Selecting roles and clicking <span className="font-medium">Save Assignments</span>{" "}
              will replace the user's current role set with the selection.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
              {roles.map((role) => {
                const checked = selectedRoleIds.has(role.id);
                return (
                  <label
                    key={role.id}
                    aria-label={`Assign role ${role.name}`}
                    className={`flex items-center gap-2 p-2 rounded-md border cursor-pointer transition-colors ${
                      checked
                        ? "bg-brand-500/5 border-brand-500/40"
                        : "border-[var(--border-primary)] hover:bg-[var(--bg-elevated)]"
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggleRole(role.id)}
                      className="w-4 h-4 rounded"
                    />
                    <div className="min-w-0">
                      <div className="text-sm font-medium text-[var(--text-primary)] truncate">
                        {role.name}
                      </div>
                      <div className="text-xs text-[var(--text-muted)]">
                        {role.permission_ids.length} perms
                      </div>
                    </div>
                  </label>
                );
              })}
            </div>
          </Card>
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main RbacAdmin page
// ---------------------------------------------------------------------------

export default function RbacAdmin() {
  const { notify } = useNotify();
  const [activeTab, setActiveTab] = useState<TabId>("roles");
  const [roles, setRoles] = useState<Role[]>([]);
  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [rolesLoading, setRolesLoading] = useState(true);
  const [permsLoading, setPermsLoading] = useState(true);
  const [rolesError, setRolesError] = useState<string | null>(null);
  const [permsError, setPermsError] = useState<string | null>(null);

  const [roleModalOpen, setRoleModalOpen] = useState(false);
  const [editingRole, setEditingRole] = useState<Role | null>(null);
  const [permModalOpen, setPermModalOpen] = useState(false);

  const fetchRoles = useCallback(async () => {
    setRolesLoading(true);
    setRolesError(null);
    try {
      // Request a large page size to get all roles in one round-trip — RBAC
      // role counts are typically small (< 100).
      const data = await rbacFetch<RoleListResponse>("/api/v1/auth/roles?page=1&page_size=500");
      setRoles(data.roles ?? []);
    } catch (err) {
      setRolesError(err instanceof Error ? err.message : "unknown error");
      notify("error", "Failed to load roles");
    } finally {
      setRolesLoading(false);
    }
  }, [notify]);

  const fetchPermissions = useCallback(async () => {
    setPermsLoading(true);
    setPermsError(null);
    try {
      const data = await rbacFetch<PermissionListResponse>(
        "/api/v1/auth/permissions?page=1&page_size=500",
      );
      setPermissions(data.permissions ?? []);
    } catch (err) {
      setPermsError(err instanceof Error ? err.message : "unknown error");
      notify("error", "Failed to load permissions");
    } finally {
      setPermsLoading(false);
    }
  }, [notify]);

  useEffect(() => {
    // Load both lists on mount — they're small and the Roles tab needs the
    // permission lookup immediately.
    fetchRoles();
    fetchPermissions();
  }, [fetchRoles, fetchPermissions]);

  const openCreateRole = () => {
    setEditingRole(null);
    setRoleModalOpen(true);
  };

  const openEditRole = (role: Role) => {
    setEditingRole(role);
    setRoleModalOpen(true);
  };

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)] flex items-center gap-2">
            <Shield className="w-6 h-6 text-brand-500" />
            RBAC Administration
          </h1>
          <p className="text-sm text-[var(--text-muted)] mt-1">
            Manage roles, permissions, and user role assignments
          </p>
        </div>
      </div>

      {/* Tabs */}
      <Tabs
        tabs={[
          { id: "roles", label: "Roles", badge: roles.length },
          { id: "permissions", label: "Permissions", badge: permissions.length },
          { id: "assignments", label: "User Assignments" },
        ]}
        activeTab={activeTab}
        onChange={(id) => setActiveTab(id as TabId)}
      />

      {/* Tab content */}
      {activeTab === "roles" && (
        <RolesTab
          roles={roles}
          permissions={permissions}
          loading={rolesLoading}
          error={rolesError}
          onReload={fetchRoles}
          onEdit={openEditRole}
          onCreate={openCreateRole}
          onDeleted={fetchRoles}
        />
      )}

      {activeTab === "permissions" && (
        <PermissionsTab
          permissions={permissions}
          loading={permsLoading}
          error={permsError}
          onReload={fetchPermissions}
          onCreate={() => setPermModalOpen(true)}
        />
      )}

      {activeTab === "assignments" && <AssignmentsTab roles={roles} />}

      {/* Modals */}
      <RoleModal
        open={roleModalOpen}
        onClose={() => setRoleModalOpen(false)}
        onSaved={() => {
          fetchRoles();
        }}
        permissions={permissions}
        editingRole={editingRole}
      />
      <PermissionModal
        open={permModalOpen}
        onClose={() => setPermModalOpen(false)}
        onSaved={fetchPermissions}
      />
    </motion.div>
  );
}
