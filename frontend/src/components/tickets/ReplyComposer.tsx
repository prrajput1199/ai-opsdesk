import { Lock, Send } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { useAddComment } from "@/api/tickets";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { getErrorMessage } from "@/lib/api";
import { cn } from "@/lib/utils";

const MAX = 5000;

export function ReplyComposer({
  ticketId,
  canAddInternalNote,
  prefill,
  onPrefillConsumed,
}: {
  ticketId: number;
  canAddInternalNote: boolean;
  prefill?: string | null;
  onPrefillConsumed?: () => void;
}) {
  const [mode, setMode] = useState<"public" | "internal">("public");
  const [body, setBody] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const addComment = useAddComment(ticketId);

  useEffect(() => {
    if (prefill) {
      setMode("public");
      setBody(prefill);
      onPrefillConsumed?.();
      textareaRef.current?.focus();
    }
  }, [prefill, onPrefillConsumed]);

  async function submit() {
    const text = body.trim();
    if (!text) return;
    try {
      await addComment.mutateAsync({ body: text, is_internal: mode === "internal" });
      setBody("");
      toast.success(mode === "internal" ? "Internal note added." : "Reply sent.");
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  }

  const internal = mode === "internal";
  return (
    <div className={cn("rounded-lg border bg-white shadow-sm", internal ? "border-amber-300" : "border-slate-200")}>
      {canAddInternalNote && (
        <div className="flex gap-1 border-b border-slate-100 p-1.5" role="tablist" aria-label="Message type">
          {(["public", "internal"] as const).map((m) => (
            <button
              key={m}
              role="tab"
              aria-selected={mode === m}
              onClick={() => setMode(m)}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500",
                mode === m ? (m === "internal" ? "bg-amber-100 text-amber-900" : "bg-brand-50 text-brand-700") : "text-slate-500 hover:bg-slate-100",
              )}
            >
              {m === "internal" && <Lock className="size-3" />}
              {m === "public" ? "Public reply" : "Internal note"}
            </button>
          ))}
        </div>
      )}
      <label htmlFor="reply-body" className="sr-only">
        {internal ? "Internal note" : "Reply"}
      </label>
      <Textarea
        id="reply-body"
        ref={textareaRef}
        value={body}
        maxLength={MAX}
        onChange={(e) => setBody(e.target.value)}
        onKeyDown={(e) => {
          if ((e.ctrlKey || e.metaKey) && e.key === "Enter") void submit();
        }}
        placeholder={internal ? "Visible to support staff only…" : "Write a reply to the customer…"}
        className={cn("min-h-[110px] rounded-none border-0 shadow-none focus-visible:ring-0", internal && "bg-amber-50/40")}
      />
      <div className="flex items-center justify-between gap-3 border-t border-slate-100 px-3 py-2">
        <p className="text-xs text-slate-400">
          {internal ? "Only agents and admins can see internal notes." : "Ctrl + Enter to send"} · {body.length}/{MAX}
        </p>
        <Button size="sm" onClick={submit} loading={addComment.isPending} disabled={!body.trim()} variant={internal ? "secondary" : "default"}>
          {!addComment.isPending && <Send />} {internal ? "Add note" : "Send reply"}
        </Button>
      </div>
    </div>
  );
}
