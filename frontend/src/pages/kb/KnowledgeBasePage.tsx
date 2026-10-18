import { BookOpen, Lock, Plus, Search, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { useArticles } from "@/api/kb";
import { useCategories } from "@/api/tickets";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { Pagination } from "@/components/ui/pagination";
import { Select } from "@/components/ui/select";
import { EmptyState, ErrorState, LoadingRows } from "@/components/ui/states";
import { useAuth } from "@/context/AuthContext";
import { formatDate } from "@/lib/utils";

export default function KnowledgeBasePage() {
  const { isAdmin, isStaff } = useAuth();
  const categories = useCategories();
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");
  const [category, setCategory] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);

  useEffect(() => {
    const id = setTimeout(() => { setDebounced(search); setPage(1); }, 300);
    return () => clearTimeout(id);
  }, [search]);

  const { data, isLoading, error, refetch } = useArticles({ page, search: debounced, category, status });

  return (
    <>
      <PageHeader
        title="Knowledge base"
        description="Guides and answers to common questions."
        actions={
          <>
            <Button variant="outline" asChild><Link to="/kb/ask"><Sparkles /> Search & ask AI</Link></Button>
            {isAdmin && <Button asChild><Link to="/kb/new"><Plus /> New article</Link></Button>}
          </>
        }
      />
      <Card>
        <div className="grid gap-3 border-b border-slate-100 p-4 sm:grid-cols-3">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" aria-hidden />
            <Input className="pl-9" placeholder="Filter by title…" aria-label="Filter articles by title" value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
          <Select aria-label="Category" value={category} onChange={(e) => { setCategory(e.target.value); setPage(1); }}>
            <option value="">All categories</option>
            {categories.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </Select>
          {isAdmin && (
            <Select aria-label="Status" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
              <option value="">All statuses</option>
              <option value="published">Published</option>
              <option value="draft">Draft</option>
            </Select>
          )}
        </div>
        {isLoading ? (
          <LoadingRows />
        ) : error ? (
          <ErrorState error={error} onRetry={() => refetch()} />
        ) : !data?.results.length ? (
          <EmptyState icon={<BookOpen />} title="No articles found" description={debounced || category ? "Try a different filter." : "Articles will appear here once published."} />
        ) : (
          <>
            <ul className="divide-y divide-slate-100">
              {data.results.map((a) => (
                <li key={a.id}>
                  <Link to={`/kb/${a.id}`} className="block px-5 py-4 hover:bg-slate-50 focus-visible:bg-slate-50 focus-visible:outline-none">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-medium text-slate-900">{a.title}</p>
                      {a.status === "draft" && <Badge className="bg-amber-50 text-amber-800 ring-amber-600/20">Draft</Badge>}
                      {isStaff && a.visibility === "internal" && <Badge><Lock className="size-3" /> Internal</Badge>}
                    </div>
                    {a.summary && <p className="mt-1 line-clamp-2 text-sm text-slate-500">{a.summary}</p>}
                    <p className="mt-1.5 text-xs text-slate-400">
                      {a.category_name ?? "General"} · Updated {formatDate(a.updated_at)}
                    </p>
                  </Link>
                </li>
              ))}
            </ul>
            <Pagination page={page} pageSize={20} count={data.count} onPageChange={setPage} />
          </>
        )}
      </Card>
    </>
  );
}
