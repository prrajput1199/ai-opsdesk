import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

import { Card } from "./card";
import { Skeleton } from "./skeleton";

export function StatCard({
  label,
  value,
  hint,
  icon,
  tone = "default",
  loading,
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  icon?: ReactNode;
  tone?: "default" | "danger" | "warning" | "success";
  loading?: boolean;
}) {
  const toneClass = {
    default: "bg-brand-50 text-brand-600",
    danger: "bg-red-50 text-red-600",
    warning: "bg-amber-50 text-amber-600",
    success: "bg-emerald-50 text-emerald-600",
  }[tone];
  return (
    <Card className="p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-medium text-slate-500">{label}</p>
          {loading ? (
            <Skeleton className="mt-2 h-7 w-16" />
          ) : (
            <p className="mt-1 text-2xl font-semibold tabular-nums tracking-tight text-slate-900">{value}</p>
          )}
          {hint && !loading && <p className="mt-0.5 truncate text-xs text-slate-500">{hint}</p>}
        </div>
        {icon && <div className={cn("rounded-lg p-2 [&_svg]:size-4", toneClass)}>{icon}</div>}
      </div>
    </Card>
  );
}
