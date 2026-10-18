import { zodResolver } from "@hookform/resolvers/zod";
import { Search, UserPlus } from "lucide-react";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { useCreateUser, useTeams, useUpdateUser, useUsers } from "@/api/admin";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { Pagination } from "@/components/ui/pagination";
import { Select } from "@/components/ui/select";
import { EmptyState, ErrorState, LoadingRows } from "@/components/ui/states";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { useAuth } from "@/context/AuthContext";
import { getErrorMessage, getFieldErrors } from "@/lib/api";
import type { AdminUser } from "@/lib/types";
import { timeAgo } from "@/lib/utils";

const createSchema = z.object({
  first_name: z.string().trim().min(1, "Required"),
  last_name: z.string().trim().min(1, "Required"),
  email: z.string().trim().email("Enter a valid email"),
  role: z.enum(["AGENT", "ADMIN"]),
  team_id: z.string().optional(),
  password: z.string().min(8, "At least 8 characters"),
});
type CreateValues = z.infer<typeof createSchema>;

const ROLE_STYLE = {
  ADMIN: "bg-violet-50 text-violet-700 ring-violet-600/20",
  AGENT: "bg-brand-50 text-brand-700 ring-brand-600/20",
  CUSTOMER: "bg-slate-100 text-slate-600 ring-slate-500/20",
};

function CreateUserDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const teams = useTeams(open);
  const create = useCreateUser();
  const { register, handleSubmit, reset, setError, formState: { errors } } = useForm<CreateValues>({
    resolver: zodResolver(createSchema),
    defaultValues: { role: "AGENT", team_id: "" },
  });

  const onSubmit = handleSubmit(async (v) => {
    try {
      await create.mutateAsync({ ...v, team_id: v.team_id ? Number(v.team_id) : null });
      toast.success(`${v.first_name} can now log in.`);
      reset({ role: "AGENT", team_id: "" });
      onOpenChange(false);
    } catch (e) {
      const fields = getFieldErrors(e);
      if (Object.keys(fields).length) Object.entries(fields).forEach(([k, m]) => setError((k === "non_field_errors" ? "password" : k) as keyof CreateValues, { message: m }));
      else toast.error(getErrorMessage(e));
    }
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add a staff member</DialogTitle>
          <DialogDescription>Create an agent or admin account. Share the temporary password securely; they can change it from their profile.</DialogDescription>
        </DialogHeader>
        <form onSubmit={onSubmit} className="space-y-4" noValidate>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field id="new-first" label="First name" error={errors.first_name?.message}><Input id="new-first" {...register("first_name")} /></Field>
            <Field id="new-last" label="Last name" error={errors.last_name?.message}><Input id="new-last" {...register("last_name")} /></Field>
          </div>
          <Field id="new-email" label="Email" error={errors.email?.message}><Input id="new-email" type="email" {...register("email")} /></Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field id="new-role" label="Role">
              <Select id="new-role" {...register("role")}><option value="AGENT">Agent</option><option value="ADMIN">Admin</option></Select>
            </Field>
            <Field id="new-team" label="Team">
              <Select id="new-team" {...register("team_id")}>
                <option value="">No team</option>
                {teams.data?.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
              </Select>
            </Field>
          </div>
          <Field id="new-password" label="Temporary password" error={errors.password?.message}>
            <Input id="new-password" type="password" autoComplete="new-password" {...register("password")} />
          </Field>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button type="submit" loading={create.isPending}>Create account</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function UserRow({ u, me }: { u: AdminUser; me: number }) {
  const teams = useTeams();
  const update = useUpdateUser();
  const [confirm, setConfirm] = useState(false);
  const isStaffUser = u.role !== "CUSTOMER";

  const patch = async (input: Parameters<typeof update.mutateAsync>[0], msg: string) => {
    try {
      await update.mutateAsync(input);
      toast.success(msg);
    } catch (e) {
      toast.error(getErrorMessage(e));
    }
  };

  return (
    <TR className={u.is_active ? "" : "bg-slate-50/60 text-slate-400"}>
      <TD>
        <p className="font-medium text-slate-900">{u.name} {u.id === me && <span className="text-xs font-normal text-slate-400">(you)</span>}</p>
        <p className="text-xs text-slate-500">{u.email}</p>
      </TD>
      <TD>
        {isStaffUser && u.id !== me ? (
          <Select aria-label={`Role for ${u.name}`} className="h-8 w-28 text-xs" value={u.role} disabled={update.isPending}
            onChange={(e) => patch({ id: u.id, role: e.target.value as AdminUser["role"] }, "Role updated.")}>
            <option value="AGENT">Agent</option><option value="ADMIN">Admin</option>
          </Select>
        ) : (
          <Badge className={ROLE_STYLE[u.role]}>{u.role.charAt(0) + u.role.slice(1).toLowerCase()}</Badge>
        )}
      </TD>
      <TD>
        {isStaffUser ? (
          <Select aria-label={`Team for ${u.name}`} className="h-8 w-40 text-xs" value={u.team?.id ?? ""} disabled={update.isPending}
            onChange={(e) => patch({ id: u.id, team_id: e.target.value ? Number(e.target.value) : null }, "Team updated.")}>
            <option value="">No team</option>
            {teams.data?.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </Select>
        ) : <span className="text-slate-400">—</span>}
      </TD>
      <TD className="text-right tabular-nums">{isStaffUser ? u.open_ticket_count : "—"}</TD>
      <TD className="whitespace-nowrap text-slate-500">{u.last_login ? timeAgo(u.last_login) : "Never"}</TD>
      <TD>
        {u.is_active ? <Badge className="bg-emerald-50 text-emerald-700 ring-emerald-600/20">Active</Badge> : <Badge>Deactivated</Badge>}
      </TD>
      <TD className="text-right">
        {u.id !== me && (
          u.is_active ? (
            <Button variant="ghost" size="sm" className="text-red-600 hover:bg-red-50" onClick={() => setConfirm(true)}>Deactivate</Button>
          ) : (
            <Button variant="ghost" size="sm" onClick={() => patch({ id: u.id, is_active: true }, "Account reactivated.")} loading={update.isPending}>Reactivate</Button>
          )
        )}
        <ConfirmDialog
          open={confirm}
          onOpenChange={setConfirm}
          title={`Deactivate ${u.name}?`}
          description="They will be signed out everywhere and won't be able to log in. Their tickets and history are kept."
          confirmLabel="Deactivate"
          destructive
          loading={update.isPending}
          onConfirm={async () => {
            await patch({ id: u.id, is_active: false }, "Account deactivated.");
            setConfirm(false);
          }}
        />
      </TD>
    </TR>
  );
}

export default function UsersPage() {
  const { user } = useAuth();
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");
  const [role, setRole] = useState("");
  const [active, setActive] = useState("");
  const [page, setPage] = useState(1);
  const [createOpen, setCreateOpen] = useState(false);

  useEffect(() => {
    const id = setTimeout(() => { setDebounced(search); setPage(1); }, 300);
    return () => clearTimeout(id);
  }, [search]);

  const { data, isLoading, error, refetch } = useUsers({ page, search: debounced, role, is_active: active });

  return (
    <>
      <PageHeader title="Users & agents" description="Create staff accounts, assign teams and manage access."
        actions={<Button onClick={() => setCreateOpen(true)}><UserPlus /> Add staff member</Button>} />
      <Card>
        <div className="grid gap-3 border-b border-slate-100 p-4 sm:grid-cols-3">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" aria-hidden />
            <Input className="pl-9" placeholder="Search name or email…" aria-label="Search users" value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
          <Select aria-label="Role" value={role} onChange={(e) => { setRole(e.target.value); setPage(1); }}>
            <option value="">All roles</option><option value="ADMIN">Admins</option><option value="AGENT">Agents</option><option value="CUSTOMER">Customers</option>
          </Select>
          <Select aria-label="Status" value={active} onChange={(e) => { setActive(e.target.value); setPage(1); }}>
            <option value="">Active and deactivated</option><option value="true">Active only</option><option value="false">Deactivated only</option>
          </Select>
        </div>
        {isLoading ? <LoadingRows /> : error ? <ErrorState error={error} onRetry={() => refetch()} /> : !data?.results.length ? (
          <EmptyState title="No users found" />
        ) : (
          <>
            <Table>
              <THead><TR><TH>User</TH><TH>Role</TH><TH>Team</TH><TH className="text-right">Open tickets</TH><TH>Last login</TH><TH>Status</TH><TH><span className="sr-only">Actions</span></TH></TR></THead>
              <TBody>{data.results.map((u) => <UserRow key={u.id} u={u} me={user!.id} />)}</TBody>
            </Table>
            <Pagination page={page} pageSize={20} count={data.count} onPageChange={setPage} />
          </>
        )}
      </Card>
      <CreateUserDialog open={createOpen} onOpenChange={setCreateOpen} />
    </>
  );
}
