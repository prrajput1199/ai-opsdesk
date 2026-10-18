import { BookOpen } from "lucide-react";
import { Link } from "react-router-dom";

import { useRelatedArticles } from "@/api/tickets";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export function RelatedArticles({ ticketId }: { ticketId: number }) {
  const { data, isLoading, isError } = useRelatedArticles(ticketId);
  return (
    <Card>
      <CardHeader className="flex-row items-center gap-2">
        <BookOpen className="size-4 text-slate-400" />
        <CardTitle>Related articles</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="space-y-2"><Skeleton className="h-4 w-4/5" /><Skeleton className="h-4 w-3/5" /></div>
        ) : isError ? (
          <p className="text-sm text-slate-500">Couldn't load related articles.</p>
        ) : !data?.length ? (
          <p className="text-sm text-slate-500">No matching articles found.</p>
        ) : (
          <ul className="space-y-2.5">
            {data.map((a) => (
              <li key={a.id}>
                <Link to={`/kb/${a.id}`} className="text-sm font-medium text-brand-700 hover:underline">{a.title}</Link>
                <div className="mt-0.5 flex gap-1.5">
                  {a.category_name && <span className="text-xs text-slate-500">{a.category_name}</span>}
                  {a.visibility === "internal" && <Badge className="py-0 text-[10px]">Internal</Badge>}
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
