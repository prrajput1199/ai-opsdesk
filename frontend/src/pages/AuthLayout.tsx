import { Sparkles } from "lucide-react";
import type { ReactNode } from "react";

export function AuthLayout({ title, subtitle, children, footer }: { title: string; subtitle: string; children: ReactNode; footer?: ReactNode }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="hidden flex-col justify-between bg-gradient-to-br from-brand-700 via-brand-600 to-violet-600 p-10 text-white lg:flex">
        <div className="flex items-center gap-2.5">
          <div className="flex size-9 items-center justify-center rounded-lg bg-white/15"><Sparkles className="size-5" /></div>
          <span className="text-lg font-semibold">AI OpsDesk</span>
        </div>
        <div className="max-w-md space-y-4">
          <h2 className="text-3xl font-semibold leading-tight">Resolve support tickets faster with AI that stays under your control.</h2>
          <ul className="space-y-2 text-sm text-blue-100">
            <li>• Automatic triage: category, priority and summary on every ticket</li>
            <li>• Reply drafts grounded in your knowledge base, approved by agents</li>
            <li>• SLA tracking and workload analytics from live data</li>
          </ul>
        </div>
        <p className="text-xs text-blue-200">Django · DRF · PostgreSQL · React · Gemini</p>
      </div>
      <div className="flex items-center justify-center px-4 py-10 sm:px-8">
        <div className="w-full max-w-sm">
          <div className="mb-8 flex items-center gap-2 lg:hidden">
            <div className="flex size-8 items-center justify-center rounded-lg bg-brand-600 text-white"><Sparkles className="size-4" /></div>
            <span className="font-semibold text-slate-900">AI OpsDesk</span>
          </div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{title}</h1>
          <p className="mt-1 text-sm text-slate-500">{subtitle}</p>
          <div className="mt-8">{children}</div>
          {footer && <div className="mt-6 text-center text-sm text-slate-500">{footer}</div>}
        </div>
      </div>
    </div>
  );
}
