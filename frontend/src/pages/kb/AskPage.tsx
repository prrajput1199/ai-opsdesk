import { AlertCircle, BookOpen, Search, Sparkles } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { useArticleSearch, useAskKnowledgeBase } from "@/api/kb";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState, LoadingRows } from "@/components/ui/states";
import { useAuth } from "@/context/AuthContext";
import { getErrorMessage } from "@/lib/api";

/** Server highlights matches as <<word>>; render them safely as <mark>. */
function Highlight({ text }: { text: string }) {
  return (
    <>
      {text.split(/(<<[^>]*>>)/g).map((part, i) =>
        part.startsWith("<<") ? <mark key={i} className="rounded bg-yellow-100 px-0.5 text-slate-900">{part.slice(2, -2)}</mark> : part,
      )}
    </>
  );
}

export default function AskPage() {
  const { hasRole } = useAuth();
  const [input, setInput] = useState("");
  const [query, setQuery] = useState("");
  const search = useArticleSearch(query);
  const ask = useAskKnowledgeBase();

  useEffect(() => {
    const id = setTimeout(() => setQuery(input.trim()), 300);
    return () => clearTimeout(id);
  }, [input]);

  function onAsk(e: FormEvent) {
    e.preventDefault();
    if (input.trim().length >= 5) ask.mutate(input.trim());
  }

  const answer = ask.data;

  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader title="Search & ask AI" description="Search the knowledge base, or ask a question and get an answer based only on our articles." />
      <form onSubmit={onAsk} className="mb-6 flex flex-col gap-2 sm:flex-row" role="search">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" aria-hidden />
          <Input
            className="h-11 pl-9 text-base"
            placeholder="e.g. How do I get a refund for a duplicate charge?"
            aria-label="Search or ask a question"
            value={input}
            maxLength={500}
            onChange={(e) => setInput(e.target.value)}
          />
        </div>
        <Button type="submit" variant="ai" size="lg" className="h-11" loading={ask.isPending} disabled={input.trim().length < 5}>
          {!ask.isPending && <Sparkles />} Ask AI
        </Button>
      </form>

      {(ask.isPending || answer || ask.isError) && (
        <Card className="mb-6 overflow-hidden border-violet-200">
          <CardHeader className="flex-row items-center gap-2 bg-gradient-to-r from-violet-50 to-brand-50">
            <Sparkles className="size-4 text-violet-600" />
            <CardTitle>{ask.isPending ? "Thinking…" : "Answer"}</CardTitle>
          </CardHeader>
          <CardContent aria-live="polite">
            {ask.isPending ? (
              <div className="space-y-2"><Skeleton className="h-4 w-full" /><Skeleton className="h-4 w-11/12" /><Skeleton className="h-4 w-2/3" /></div>
            ) : ask.isError ? (
              <Alert variant="warning" title="The AI assistant is unavailable">
                {getErrorMessage(ask.error)} You can still use the article search below.
              </Alert>
            ) : answer ? (
              <div className="space-y-4">
                {!answer.sufficient_information && (
                  <Alert variant="info" title="Not covered by the knowledge base">
                    The articles don't fully answer this.{" "}
                    {hasRole("CUSTOMER") ? <Link to="/tickets/new" className="font-medium underline">Create a ticket</Link> : "Consider writing an article for it."}
                  </Alert>
                )}
                <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-800">{answer.answer}</p>
                {answer.citations.length > 0 && (
                  <div>
                    <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500">Sources</p>
                    <ul className="flex flex-wrap gap-2">
                      {answer.citations.map((c, i) => (
                        <li key={c.id}>
                          <Link to={`/kb/${c.id}`} className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-brand-700 hover:bg-brand-50">
                            <span className="text-slate-400">[{i + 1}]</span> {c.title}
                          </Link>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                <p className="flex items-center gap-1.5 text-xs text-slate-400">
                  <AlertCircle className="size-3.5" />
                  {answer.ai_generated ? "AI-generated from the articles above. Check the sources for details." : "No AI was used: no matching articles were found."}
                </p>
              </div>
            ) : null}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader className="flex-row items-center gap-2">
          <BookOpen className="size-4 text-slate-400" />
          <CardTitle>Matching articles</CardTitle>
        </CardHeader>
        {query.length < 2 ? (
          <EmptyState icon={<Search />} title="Start typing to search" description="Results update as you type. Press Ask AI for a written answer." />
        ) : search.isLoading ? (
          <LoadingRows rows={3} />
        ) : search.isError ? (
          <ErrorState error={search.error} onRetry={() => search.refetch()} />
        ) : !search.data?.length ? (
          <EmptyState title="No articles match" description="Try other keywords, or ask the AI." />
        ) : (
          <ul className="divide-y divide-slate-100">
            {search.data.map((a) => (
              <li key={a.id}>
                <Link to={`/kb/${a.id}`} className="block px-5 py-4 hover:bg-slate-50">
                  <p className="font-medium text-slate-900">{a.title}</p>
                  {a.headline && <p className="mt-1 text-sm text-slate-500"><Highlight text={a.headline} /></p>}
                  <p className="mt-1 text-xs text-slate-400">{a.category_name ?? "General"}</p>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
