import { PlusCircle, SearchX } from "lucide-react";
import { useMemo } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { useTickets, type TicketQuery } from "@/api/tickets";
import { TicketFilters } from "@/components/tickets/TicketFilters";
import { TicketTable } from "@/components/tickets/TicketTable";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { Pagination } from "@/components/ui/pagination";
import { EmptyState, ErrorState, LoadingRows } from "@/components/ui/states";
import { useAuth } from "@/context/AuthContext";

const PAGE_SIZE = 20;
const ARRAY_KEYS = ["status", "priority"] as const;
const STRING_KEYS = ["search", "category", "assigned_agent", "created_after", "created_before", "sla", "ordering"] as const;

/** Filters live in the URL so they survive reloads and can be shared. */
function useTicketQuery(): [TicketQuery, (q: TicketQuery) => void] {
  const [params, setParams] = useSearchParams();
  const query = useMemo<TicketQuery>(() => {
    const q: TicketQuery = { page: Number(params.get("page") || 1), page_size: PAGE_SIZE };
    ARRAY_KEYS.forEach((k) => {
      const v = params.getAll(k);
      if (v.length) q[k] = v;
    });
    STRING_KEYS.forEach((k) => {
      const v = params.get(k);
      if (v) q[k] = v;
    });
    return q;
  }, [params]);

  const update = (q: TicketQuery) => {
    const next = new URLSearchParams();
    Object.entries(q).forEach(([k, v]) => {
      if (k === "page_size" || v === undefined || v === "" || (k === "page" && v === 1)) return;
      if (Array.isArray(v)) v.forEach((item) => next.append(k, item));
      else next.set(k, String(v));
    });
    setParams(next);
  };
  return [query, update];
}

export default function TicketsPage() {
  const { isStaff, hasRole } = useAuth();
  const [query, setQuery] = useTicketQuery();
  const { data, isLoading, isFetching, error, refetch } = useTickets(query);
  const filtered = Object.keys(query).some((k) => !["page", "page_size", "ordering"].includes(k));

  return (
    <>
      <PageHeader
        title={isStaff ? "Ticket queue" : "My tickets"}
        description={isStaff ? "Tickets you can access, based on your role and team." : "All the requests you've sent to support."}
        actions={hasRole("CUSTOMER") && <Button asChild><Link to="/tickets/new"><PlusCircle /> New ticket</Link></Button>}
      />
      <Card>
        <TicketFilters value={query} onChange={setQuery} isStaff={isStaff} />
        <div aria-busy={isFetching} className={isFetching && !isLoading ? "opacity-60 transition-opacity" : ""}>
          {isLoading ? (
            <LoadingRows rows={6} />
          ) : error ? (
            <ErrorState error={error} onRetry={() => refetch()} />
          ) : !data?.results.length ? (
            filtered ? (
              <EmptyState icon={<SearchX />} title="No tickets match these filters" description="Try removing a filter or searching for something else." />
            ) : (
              <EmptyState
                title="No tickets yet"
                description={isStaff ? "New tickets from customers will appear here." : "Need help? Create a ticket and our team will get back to you."}
                action={hasRole("CUSTOMER") && <Button asChild><Link to="/tickets/new">Create a ticket</Link></Button>}
              />
            )
          ) : (
            <>
              <TicketTable tickets={data.results} showCustomer={isStaff} />
              <Pagination page={query.page ?? 1} pageSize={PAGE_SIZE} count={data.count} onPageChange={(page) => setQuery({ ...query, page })} />
            </>
          )}
        </div>
      </Card>
    </>
  );
}
