import { ArrowLeft, Lock, Pencil, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";

import { useArticle, useDeleteArticle } from "@/api/kb";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/states";
import { useAuth } from "@/context/AuthContext";
import { getErrorMessage } from "@/lib/api";
import { formatDate } from "@/lib/utils";

import NotFoundPage from "../NotFoundPage";

/** Renders plain text with **bold** support and paragraph breaks (no HTML injection). */
function ArticleBody({ content }: { content: string }) {
  return (
    <div className="space-y-4 text-[15px] leading-7 text-slate-700">
      {content.split(/\n{2,}/).map((para, i) => (
        <p key={i} className="whitespace-pre-wrap">
          {para.split(/(\*\*[^*]+\*\*)/g).map((part, j) =>
            part.startsWith("**") && part.endsWith("**") ? <strong key={j} className="font-semibold text-slate-900">{part.slice(2, -2)}</strong> : part,
          )}
        </p>
      ))}
    </div>
  );
}

export default function ArticlePage() {
  const id = Number(useParams().id);
  const { isAdmin, isStaff } = useAuth();
  const navigate = useNavigate();
  const { data, isLoading, error, refetch } = useArticle(id);
  const remove = useDeleteArticle();
  const [confirm, setConfirm] = useState(false);

  if (isLoading) return <div className="space-y-3"><Skeleton className="h-8 w-1/2" /><Skeleton className="h-40 w-full" /></div>;
  if (error) {
    if ((error as { response?: { status?: number } }).response?.status === 404) return <NotFoundPage />;
    return <Card><ErrorState error={error} onRetry={() => refetch()} /></Card>;
  }
  const a = data!;

  return (
    <div className="mx-auto max-w-3xl">
      <Link to="/kb" className="mb-4 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-900">
        <ArrowLeft className="size-4" /> Knowledge base
      </Link>
      <Card>
        <CardContent className="p-6 sm:p-8">
          <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
            <span>{a.category_name ?? "General"}</span>
            <span aria-hidden>·</span>
            <span>Updated {formatDate(a.updated_at)}</span>
            {a.status === "draft" && <Badge className="bg-amber-50 text-amber-800 ring-amber-600/20">Draft</Badge>}
            {isStaff && a.visibility === "internal" && <Badge><Lock className="size-3" /> Internal — staff only</Badge>}
          </div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{a.title}</h1>
          {a.summary && <p className="mt-2 text-slate-500">{a.summary}</p>}
          <hr className="my-6 border-slate-100" />
          <ArticleBody content={a.content} />
          {isAdmin && (
            <div className="mt-8 flex gap-2 border-t border-slate-100 pt-4">
              <Button variant="outline" size="sm" asChild><Link to={`/kb/${a.id}/edit`}><Pencil /> Edit</Link></Button>
              <Button variant="ghost" size="sm" className="text-red-600 hover:bg-red-50" onClick={() => setConfirm(true)}><Trash2 /> Delete</Button>
            </div>
          )}
        </CardContent>
      </Card>
      <ConfirmDialog
        open={confirm}
        onOpenChange={setConfirm}
        title="Delete this article?"
        description="This permanently removes the article. AI answers will no longer cite it."
        confirmLabel="Delete"
        destructive
        loading={remove.isPending}
        onConfirm={async () => {
          try {
            await remove.mutateAsync(a.id);
            toast.success("Article deleted.");
            navigate("/kb");
          } catch (e) {
            toast.error(getErrorMessage(e));
          }
        }}
      />
    </div>
  );
}
