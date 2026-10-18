import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { z } from "zod";

import { useArticle, useSaveArticle } from "@/api/kb";
import { useCategories } from "@/api/tickets";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { LoadingRows } from "@/components/ui/states";
import { Textarea } from "@/components/ui/textarea";
import { getErrorMessage, getFieldErrors } from "@/lib/api";

const schema = z.object({
  title: z.string().trim().min(3, "At least 3 characters").max(200),
  summary: z.string().trim().max(300, "Maximum 300 characters").optional(),
  content: z.string().trim().min(20, "At least 20 characters").max(20000),
  category: z.string().optional(),
  status: z.enum(["draft", "published"]),
  visibility: z.enum(["public", "internal"]),
});
type FormValues = z.infer<typeof schema>;

export default function ArticleEditorPage() {
  const params = useParams();
  const id = params.id ? Number(params.id) : undefined;
  const navigate = useNavigate();
  const existing = useArticle(id ?? NaN);
  const categories = useCategories();
  const save = useSaveArticle(id);
  const { register, handleSubmit, reset, setError, formState: { errors, isDirty } } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { title: "", summary: "", content: "", category: "", status: "draft", visibility: "public" },
  });

  useEffect(() => {
    if (existing.data) {
      const a = existing.data;
      reset({ title: a.title, summary: a.summary, content: a.content, category: a.category ? String(a.category) : "", status: a.status, visibility: a.visibility });
    }
  }, [existing.data, reset]);

  const onSubmit = handleSubmit(async (v) => {
    try {
      const article = await save.mutateAsync({ ...v, summary: v.summary ?? "", category: v.category ? Number(v.category) : null });
      toast.success(id ? "Article updated." : "Article created.");
      navigate(`/kb/${article.id}`);
    } catch (error) {
      Object.entries(getFieldErrors(error)).forEach(([k, m]) => setError(k as keyof FormValues, { message: m }));
    }
  });

  if (id && existing.isLoading) return <LoadingRows />;

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader title={id ? "Edit article" : "New article"} description="Published public articles are visible to customers and used by the AI assistant." />
      <Card>
        <CardContent className="pt-5">
          <form onSubmit={onSubmit} className="space-y-5" noValidate>
            {save.isError && !Object.keys(getFieldErrors(save.error)).length && <Alert variant="error">{getErrorMessage(save.error)}</Alert>}
            <Field id="title" label="Title" required error={errors.title?.message}>
              <Input id="title" aria-invalid={!!errors.title} {...register("title")} />
            </Field>
            <Field id="summary" label="Summary" error={errors.summary?.message} hint="One or two sentences shown in lists.">
              <Input id="summary" {...register("summary")} />
            </Field>
            <div className="grid gap-4 sm:grid-cols-3">
              <Field id="category" label="Category">
                <Select id="category" {...register("category")}>
                  <option value="">General</option>
                  {categories.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </Select>
              </Field>
              <Field id="status" label="Status">
                <Select id="status" {...register("status")}>
                  <option value="draft">Draft</option>
                  <option value="published">Published</option>
                </Select>
              </Field>
              <Field id="visibility" label="Visibility">
                <Select id="visibility" {...register("visibility")}>
                  <option value="public">Public</option>
                  <option value="internal">Internal (staff only)</option>
                </Select>
              </Field>
            </div>
            <Field id="content" label="Content" required error={errors.content?.message} hint="Plain text. Blank lines start new paragraphs; **text** is bold.">
              <Textarea id="content" rows={14} aria-invalid={!!errors.content} {...register("content")} />
            </Field>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => navigate(-1)}>Cancel</Button>
              <Button type="submit" loading={save.isPending} disabled={!!id && !isDirty}>Save article</Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
