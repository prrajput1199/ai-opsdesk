import { Plus, Save } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { useSaveCategory, useSaveTeam, useSLAPolicies, useTeams, useUpdateSLAPolicy } from "@/api/admin";
import { useCategories } from "@/api/tickets";
import { PriorityBadge } from "@/components/tickets/badges";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { ErrorState, LoadingRows } from "@/components/ui/states";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { getErrorMessage } from "@/lib/api";
import type { SLAPolicy } from "@/lib/types";

function notify(p: Promise<unknown>, msg: string) {
  return p.then(() => toast.success(msg)).catch((e) => toast.error(getErrorMessage(e)));
}

function SLARow({ policy }: { policy: SLAPolicy }) {
  const update = useUpdateSLAPolicy();
  const [hours, setHours] = useState(String(policy.resolution_hours));
  useEffect(() => setHours(String(policy.resolution_hours)), [policy.resolution_hours]);
  const changed = Number(hours) !== policy.resolution_hours;
  return (
    <TR>
      <TD><PriorityBadge priority={policy.priority} /></TD>
      <TD>
        <div className="flex items-center gap-2">
          <Input type="number" min={1} max={2160} className="h-8 w-24" aria-label={`${policy.priority_label} resolution hours`} value={hours} onChange={(e) => setHours(e.target.value)} />
          <span className="text-xs text-slate-500">hours</span>
        </div>
      </TD>
      <TD className="text-right">
        <Button size="sm" variant="outline" disabled={!changed || !Number(hours)} loading={update.isPending}
          onClick={() => notify(update.mutateAsync({ id: policy.id, resolution_hours: Number(hours) }), "SLA target updated.")}>
          {!update.isPending && <Save />} Save
        </Button>
      </TD>
    </TR>
  );
}

export default function SettingsPage() {
  const categories = useCategories();
  const teams = useTeams();
  const sla = useSLAPolicies();
  const saveCategory = useSaveCategory();
  const saveTeam = useSaveTeam();
  const [newCategory, setNewCategory] = useState("");
  const [newCategoryTeam, setNewCategoryTeam] = useState("");
  const [newTeam, setNewTeam] = useState("");

  return (
    <>
      <PageHeader title="Categories, teams & SLA" description="Configure how tickets are routed and how fast they must be resolved." />
      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>SLA targets</CardTitle>
            <CardDescription>Resolution time per priority. Applies to new tickets and when a ticket's priority changes.</CardDescription>
          </CardHeader>
          {sla.isLoading ? <LoadingRows rows={4} /> : sla.error ? <ErrorState error={sla.error} onRetry={() => sla.refetch()} /> : (
            <Table>
              <THead><TR><TH>Priority</TH><TH>Resolve within</TH><TH><span className="sr-only">Save</span></TH></TR></THead>
              <TBody>{sla.data!.map((p) => <SLARow key={p.id} policy={p} />)}</TBody>
            </Table>
          )}
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Teams</CardTitle>
            <CardDescription>Agents see every ticket in categories routed to their team.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <form className="flex gap-2" onSubmit={(e) => {
              e.preventDefault();
              if (!newTeam.trim()) return;
              notify(saveTeam.mutateAsync({ name: newTeam.trim() }), "Team created.").then(() => setNewTeam(""));
            }}>
              <Input placeholder="New team name" aria-label="New team name" value={newTeam} onChange={(e) => setNewTeam(e.target.value)} maxLength={100} />
              <Button type="submit" variant="outline" loading={saveTeam.isPending}>{!saveTeam.isPending && <Plus />} Add</Button>
            </form>
            {teams.isLoading ? <LoadingRows rows={2} /> : (
              <ul className="divide-y divide-slate-100 rounded-lg border border-slate-100">
                {teams.data?.map((t) => (
                  <li key={t.id} className="flex items-center justify-between px-3 py-2.5 text-sm">
                    <span className="font-medium text-slate-900">{t.name}</span>
                    <span className="text-xs text-slate-500">{t.member_count} active member{t.member_count === 1 ? "" : "s"}</span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>

      <Card className="mt-6">
        <CardHeader>
          <CardTitle>Ticket categories</CardTitle>
          <CardDescription>Customers pick a category when creating tickets; the AI suggests one from this list. Deactivate instead of deleting to keep history.</CardDescription>
        </CardHeader>
        <CardContent className="border-b border-slate-100">
          <form className="flex flex-col gap-2 sm:flex-row" onSubmit={(e) => {
            e.preventDefault();
            if (!newCategory.trim()) return;
            notify(saveCategory.mutateAsync({ name: newCategory.trim(), team: newCategoryTeam ? Number(newCategoryTeam) : null }), "Category created.")
              .then(() => { setNewCategory(""); setNewCategoryTeam(""); });
          }}>
            <Input placeholder="New category name" aria-label="New category name" value={newCategory} onChange={(e) => setNewCategory(e.target.value)} maxLength={80} />
            <Select aria-label="Route to team" className="sm:w-48" value={newCategoryTeam} onChange={(e) => setNewCategoryTeam(e.target.value)}>
              <option value="">Shared queue (no team)</option>
              {teams.data?.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </Select>
            <Button type="submit" variant="outline" loading={saveCategory.isPending}>{!saveCategory.isPending && <Plus />} Add category</Button>
          </form>
        </CardContent>
        {categories.isLoading ? <LoadingRows /> : categories.error ? <ErrorState error={categories.error} onRetry={() => categories.refetch()} /> : (
          <Table>
            <THead><TR><TH>Name</TH><TH>Routed to</TH><TH>Status</TH><TH><span className="sr-only">Actions</span></TH></TR></THead>
            <TBody>
              {categories.data!.map((c) => (
                <TR key={c.id}>
                  <TD><span className="font-medium text-slate-900">{c.name}</span>{c.description && <span className="block text-xs text-slate-500">{c.description}</span>}</TD>
                  <TD>
                    <Select aria-label={`Team for ${c.name}`} className="h-8 w-48 text-xs" value={c.team ?? ""}
                      onChange={(e) => notify(saveCategory.mutateAsync({ id: c.id, team: e.target.value ? Number(e.target.value) : null }), "Routing updated.")}>
                      <option value="">Shared queue (no team)</option>
                      {teams.data?.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
                    </Select>
                  </TD>
                  <TD>{c.is_active ? <Badge className="bg-emerald-50 text-emerald-700 ring-emerald-600/20">Active</Badge> : <Badge>Inactive</Badge>}</TD>
                  <TD className="text-right">
                    <Button variant="ghost" size="sm" onClick={() => notify(saveCategory.mutateAsync({ id: c.id, is_active: !c.is_active }), c.is_active ? "Category deactivated." : "Category activated.")}>
                      {c.is_active ? "Deactivate" : "Activate"}
                    </Button>
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        )}
      </Card>
    </>
  );
}
