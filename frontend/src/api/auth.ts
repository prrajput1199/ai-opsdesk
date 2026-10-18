import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";

import { api } from "@/lib/api";
import type { User } from "@/lib/types";

export const meKey = ["me"] as const;

/**
 * Switch the cached user without detaching the `me` query that AuthProvider observes
 * (queryClient.clear() would orphan it), and drop everything cached for the previous user.
 */
function switchUser(qc: ReturnType<typeof useQueryClient>, user: User | null) {
  qc.removeQueries({ predicate: (query) => query.queryKey[0] !== meKey[0] });
  qc.setQueryData(meKey, user);
}

export function useMe() {
  return useQuery({
    queryKey: meKey,
    queryFn: async (): Promise<User | null> => {
      try {
        return (await api.get<User>("/auth/me/")).data;
      } catch (error) {
        if (axios.isAxiosError(error) && error.response?.status === 401) return null; // not logged in
        throw error;
      }
    },
    staleTime: 5 * 60_000,
    retry: false,
  });
}

export interface LoginInput {
  email: string;
  password: string;
}
export interface RegisterInput extends LoginInput {
  first_name: string;
  last_name: string;
}

export function useLogin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: LoginInput) => (await api.post<User>("/auth/login/", input)).data,
    onSuccess: (user) => switchUser(qc, user),
  });
}

export function useRegister() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: RegisterInput) => (await api.post<User>("/auth/register/", input)).data,
    onSuccess: (user) => switchUser(qc, user),
  });
}

export function useLogout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      await api.post("/auth/logout/");
    },
    onSettled: () => switchUser(qc, null),
  });
}

export function useUpdateProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: { first_name: string; last_name: string }) =>
      (await api.patch<User>("/auth/me/", input)).data,
    onSuccess: (user) => qc.setQueryData(meKey, user),
  });
}

export function useChangePassword() {
  return useMutation({
    mutationFn: async (input: { current_password: string; new_password: string }) =>
      (await api.post("/auth/change-password/", input)).data,
  });
}
