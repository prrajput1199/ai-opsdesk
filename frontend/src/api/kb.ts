import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { Article, ArticleDetail, KnowledgeAnswer, Paginated, SearchResult } from "@/lib/types";

export interface ArticleQuery {
  page?: number;
  search?: string;
  category?: string;
  status?: string;
  visibility?: string;
}

export function useArticles(q: ArticleQuery) {
  return useQuery({
    queryKey: ["kb", "list", q],
    queryFn: async () => {
      const params = Object.fromEntries(Object.entries(q).filter(([, v]) => v !== "" && v !== undefined));
      return (await api.get<Paginated<Article>>("/knowledge-base/articles/", { params })).data;
    },
    placeholderData: keepPreviousData,
  });
}

export function useArticle(id: number) {
  return useQuery({
    queryKey: ["kb", "detail", id],
    queryFn: async () => (await api.get<ArticleDetail>(`/knowledge-base/articles/${id}/`)).data,
    enabled: Number.isFinite(id),
  });
}

export function useArticleSearch(q: string) {
  return useQuery({
    queryKey: ["kb", "search", q],
    queryFn: async () => (await api.get<SearchResult[]>("/knowledge-base/search/", { params: { q } })).data,
    enabled: q.trim().length >= 2,
    placeholderData: keepPreviousData,
  });
}

export function useAskKnowledgeBase() {
  return useMutation({
    mutationFn: async (question: string) =>
      (await api.post<KnowledgeAnswer>("/knowledge-base/ask/", { question })).data,
  });
}

export interface ArticleInput {
  title: string;
  summary?: string;
  content: string;
  category?: number | null;
  status: "draft" | "published";
  visibility: "public" | "internal";
}

export function useSaveArticle(id?: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: ArticleInput) =>
      id
        ? (await api.patch<ArticleDetail>(`/knowledge-base/articles/${id}/`, input)).data
        : (await api.post<ArticleDetail>("/knowledge-base/articles/", input)).data,
    onSuccess: (article) => {
      qc.setQueryData(["kb", "detail", article.id], article);
      qc.invalidateQueries({ queryKey: ["kb", "list"] });
      qc.invalidateQueries({ queryKey: ["kb", "search"] });
    },
  });
}

export function useDeleteArticle() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/knowledge-base/articles/${id}/`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["kb"] }),
  });
}
