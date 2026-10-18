import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { AdminUser, AuditLogEntry, Category, Paginated, Role, SLAPolicy, Team } from "@/lib/types";

// ---------------------------------------------------------------- users ---
export interface UserQuery {
  page?: number;
  search?: string;
  role?: string;
  is_active?: string;
}

export function useUsers(q: UserQuery) {
  return useQuery({
    queryKey: ["users", q],
    queryFn: async () => {
      const params = Object.fromEntries(Object.entries(q).filter(([, v]) => v !== "" && v !== undefined));
      return (await api.get<Paginated<AdminUser>>("/users/", { params })).data;
    },
    placeholderData: keepPreviousData,
  });
}

export interface CreateUserInput {
  email: string;
  first_name: string;
  last_name: string;
  role: Exclude<Role, "CUSTOMER">;
  team_id: number | null;
  password: string;
}

export function useCreateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: CreateUserInput) => (await api.post<AdminUser>("/users/", input)).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["users"] });
      qc.invalidateQueries({ queryKey: ["agents"] });
    },
  });
}

export function useUpdateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, ...input }: { id: number } & Partial<{
      first_name: string; last_name: string; role: Role; team_id: number | null; is_active: boolean;
    }>) => (await api.patch<AdminUser>(`/users/${id}/`, input)).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["users"] });
      qc.invalidateQueries({ queryKey: ["agents"] });
      qc.invalidateQueries({ queryKey: ["teams"] });
    },
  });
}

// ---------------------------------------------------------------- teams ---
export function useTeams(enabled = true) {
  return useQuery({
    queryKey: ["teams"],
    queryFn: async () => (await api.get<Team[]>("/teams/")).data,
    enabled,
  });
}

export function useSaveTeam() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, ...input }: { id?: number; name: string; description?: string }) =>
      id ? (await api.patch<Team>(`/teams/${id}/`, input)).data : (await api.post<Team>("/teams/", input)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["teams"] }),
  });
}

// ----------------------------------------------------------- categories ---
export function useSaveCategory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, ...input }: { id?: number; name?: string; description?: string; team?: number | null; is_active?: boolean }) =>
      id
        ? (await api.patch<Category>(`/categories/${id}/`, input)).data
        : (await api.post<Category>("/categories/", input)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["categories"] }),
  });
}

// ------------------------------------------------------------------ SLA ---
export function useSLAPolicies() {
  return useQuery({
    queryKey: ["sla-policies"],
    queryFn: async () => (await api.get<SLAPolicy[]>("/sla-policies/")).data,
  });
}

export function useUpdateSLAPolicy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, resolution_hours }: { id: number; resolution_hours: number }) =>
      (await api.patch<SLAPolicy>(`/sla-policies/${id}/`, { resolution_hours })).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sla-policies"] });
      qc.invalidateQueries({ queryKey: ["analytics"] });
    },
  });
}

// ---------------------------------------------------------------- audit ---
export interface AuditQuery {
  page?: number;
  search?: string;
  action?: string;
  date_from?: string;
  date_to?: string;
}

export function useAuditLogs(q: AuditQuery) {
  return useQuery({
    queryKey: ["audit", q],
    queryFn: async () => {
      const params = Object.fromEntries(Object.entries(q).filter(([, v]) => v !== "" && v !== undefined));
      return (await api.get<Paginated<AuditLogEntry>>("/audit-logs/", { params })).data;
    },
    placeholderData: keepPreviousData,
  });
}
