import { AlertCircle, CheckCircle2, Info, TriangleAlert } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

const styles = {
  info: { box: "border-blue-200 bg-blue-50 text-blue-900", Icon: Info, icon: "text-blue-500" },
  warning: { box: "border-amber-200 bg-amber-50 text-amber-900", Icon: TriangleAlert, icon: "text-amber-500" },
  error: { box: "border-red-200 bg-red-50 text-red-900", Icon: AlertCircle, icon: "text-red-500" },
  success: { box: "border-emerald-200 bg-emerald-50 text-emerald-900", Icon: CheckCircle2, icon: "text-emerald-500" },
};

export function Alert({
  variant = "info",
  title,
  children,
  className,
}: {
  variant?: keyof typeof styles;
  title?: string;
  children?: ReactNode;
  className?: string;
}) {
  const { box, Icon, icon } = styles[variant];
  return (
    <div role={variant === "error" ? "alert" : "status"} className={cn("flex gap-3 rounded-lg border p-3 text-sm", box, className)}>
      <Icon className={cn("mt-0.5 size-4 shrink-0", icon)} aria-hidden />
      <div className="min-w-0 space-y-1">
        {title && <p className="font-medium">{title}</p>}
        {children && <div className="text-[13px] leading-relaxed opacity-90">{children}</div>}
      </div>
    </div>
  );
}
