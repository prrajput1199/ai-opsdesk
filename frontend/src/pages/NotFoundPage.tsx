import { Compass } from "lucide-react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";

export default function NotFoundPage() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-3 text-center">
      <div className="rounded-full bg-slate-100 p-4 text-slate-400"><Compass className="size-8" /></div>
      <p className="text-sm font-semibold text-brand-600">404</p>
      <h1 className="text-2xl font-semibold text-slate-900">Page not found</h1>
      <p className="max-w-sm text-sm text-slate-500">The page you're looking for doesn't exist, or you don't have access to it.</p>
      <Button asChild className="mt-2"><Link to="/">Back to dashboard</Link></Button>
    </div>
  );
}
