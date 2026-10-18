import { ChevronLeft, ChevronRight } from "lucide-react";

import { Button } from "./button";

export function Pagination({
  page,
  pageSize,
  count,
  onPageChange,
}: {
  page: number;
  pageSize: number;
  count: number;
  onPageChange: (page: number) => void;
}) {
  const pages = Math.max(1, Math.ceil(count / pageSize));
  if (count === 0) return null;
  const from = (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, count);
  return (
    <nav className="flex items-center justify-between gap-3 border-t border-slate-100 px-4 py-3 text-sm" aria-label="Pagination">
      <p className="text-slate-500">
        <span className="font-medium text-slate-700">{from}</span>–<span className="font-medium text-slate-700">{to}</span> of{" "}
        <span className="font-medium text-slate-700">{count}</span>
      </p>
      <div className="flex items-center gap-2">
        <Button variant="outline" size="sm" onClick={() => onPageChange(page - 1)} disabled={page <= 1} aria-label="Previous page">
          <ChevronLeft /> <span className="hidden sm:inline">Previous</span>
        </Button>
        <span className="text-slate-500">
          {page} / {pages}
        </span>
        <Button variant="outline" size="sm" onClick={() => onPageChange(page + 1)} disabled={page >= pages} aria-label="Next page">
          <span className="hidden sm:inline">Next</span> <ChevronRight />
        </Button>
      </div>
    </nav>
  );
}
