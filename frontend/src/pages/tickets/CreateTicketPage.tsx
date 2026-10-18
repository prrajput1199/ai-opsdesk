import { zodResolver } from "@hookform/resolvers/zod";
import { BookOpen, Lightbulb } from "lucide-react";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { z } from "zod";

import { useArticleSearch } from "@/api/kb";
import { useCategories, useCreateTicket } from "@/api/tickets";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { getErrorMessage, getFieldErrors } from "@/lib/api";

const schema = z.object({
  title: z.string().trim().min(5, "Use at least 5 characters").max(200, "Keep the title under 200 characters"),
  description: z.string().trim().min(10, "Please describe the problem (at least 10 characters)").max(5000, "Maximum 5,000 characters"),
  category_id: z.string().optional(),
});
type FormValues = z.infer<typeof schema>;

function useDebounced<T>(value: T, ms: number) {
  const [v, setV] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setV(value), ms);
    return () => clearTimeout(id);
  }, [value, ms]);
  return v;
}

export default function CreateTicketPage() {
  const navigate = useNavigate();
  const categories = useCategories();
  const create = useCreateTicket();
  const { register, handleSubmit, watch, setError, formState: { errors } } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { title: "", description: "", category_id: "" },
  });
  const title = useDebounced(watch("title"), 400);
  const description = watch("description");
  const suggestions = useArticleSearch(title.length >= 5 ? title : "");

  const onSubmit = handleSubmit(async (values) => {
    try {
      const ticket = await create.mutateAsync({
        title: values.title,
        description: values.description,
        category_id: values.category_id ? Number(values.category_id) : null,
      });
      toast.success(`Ticket ${ticket.number} created. We'll get back to you soon.`);
      navigate(`/tickets/${ticket.id}`);
    } catch (error) {
      Object.entries(getFieldErrors(error)).forEach(([field, message]) => {
        const name = field === "category_id" ? "category_id" : field;
        if (["title", "description", "category_id"].includes(name)) setError(name as keyof FormValues, { message });
      });
    }
  });

  return (
    <>
      <PageHeader title="New support ticket" description="Tell us what's going on. The more detail, the faster we can help." />
      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardContent className="pt-5">
            <form onSubmit={onSubmit} className="space-y-5" noValidate>
              {create.isError && !Object.keys(getFieldErrors(create.error)).length && (
                <Alert variant="error">{getErrorMessage(create.error)}</Alert>
              )}
              <Field id="title" label="Subject" required error={errors.title?.message}>
                <Input id="title" placeholder="e.g. I was charged twice this month" aria-invalid={!!errors.title} {...register("title")} />
              </Field>
              <Field id="category_id" label="Category" hint="Optional — our AI will suggest one if you're not sure." error={errors.category_id?.message}>
                <Select id="category_id" {...register("category_id")}>
                  <option value="">I'm not sure</option>
                  {categories.data?.map((c) => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </Select>
              </Field>
              <Field id="description" label="Description" required error={errors.description?.message}
                hint={`${description.length}/5000 · Include steps to reproduce, error messages and when it started.`}>
                <Textarea id="description" rows={8} aria-invalid={!!errors.description} {...register("description")} />
              </Field>
              <div className="flex justify-end gap-2">
                <Button type="button" variant="outline" onClick={() => navigate(-1)}>Cancel</Button>
                <Button type="submit" loading={create.isPending}>Submit ticket</Button>
              </div>
            </form>
          </CardContent>
        </Card>
        <Card className="h-fit">
          <CardHeader className="flex-row items-center gap-2">
            <Lightbulb className="size-4 text-amber-500" />
            <div>
              <CardTitle>Suggested articles</CardTitle>
              <CardDescription>These might answer your question right away.</CardDescription>
            </div>
          </CardHeader>
          <CardContent>
            {title.length < 5 ? (
              <p className="text-sm text-slate-500">Start typing a subject to see related help articles.</p>
            ) : suggestions.isFetching && !suggestions.data ? (
              <p className="text-sm text-slate-500">Searching…</p>
            ) : !suggestions.data?.length ? (
              <p className="text-sm text-slate-500">No matching articles. Go ahead and submit your ticket.</p>
            ) : (
              <ul className="space-y-3">
                {suggestions.data.slice(0, 4).map((a) => (
                  <li key={a.id}>
                    <Link to={`/kb/${a.id}`} target="_blank" className="flex items-start gap-2 text-sm font-medium text-brand-700 hover:underline">
                      <BookOpen className="mt-0.5 size-4 shrink-0" /> {a.title}
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </>
  );
}
