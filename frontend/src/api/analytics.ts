import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { AgentWorkload, CategoryBreakdown, Overview, ResolutionTime, SLAReport, Trends } from "@/lib/types";

export interface RangeParams {
  date_from?: string;
  date_to?: string;
}

function useAnalytics<T>(name: string, range: RangeParams, enabled = true) {
  return useQuery({
    queryKey: ["analytics", name, range],
    queryFn: async () => {
      const params = Object.fromEntries(Object.entries(range).filter(([, v]) => v));
      return (await api.get<T>(`/analytics/${name}/`, { params })).data;
    },
    placeholderData: keepPreviousData,
    enabled,
  });
}

export const useOverview = (range: RangeParams = {}) => useAnalytics<Overview>("overview", range);
export const useTrends = (range: RangeParams = {}, enabled = true) => useAnalytics<Trends>("ticket-trends", range, enabled);
export const useCategoryBreakdown = (range: RangeParams = {}, enabled = true) =>
  useAnalytics<CategoryBreakdown>("category-breakdown", range, enabled);
export const useResolutionTime = (range: RangeParams = {}, enabled = true) =>
  useAnalytics<ResolutionTime>("resolution-time", range, enabled);
export const useSLAReport = (range: RangeParams = {}, enabled = true) => useAnalytics<SLAReport>("sla", range, enabled);
export const useAgentWorkload = (range: RangeParams = {}, enabled = true) =>
  useAnalytics<AgentWorkload>("agent-workload", range, enabled);
