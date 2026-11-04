import { env as publicEnv } from '$env/dynamic/public';
import { createClient } from './client';
import type {
  CrawlJob, PageRecord, Paged, SearchResponse, Site, Stats, Tag
} from './types';

/** `baseUrl` defaults to PUBLIC_API_BASE_URL (empty = same origin, i.e. the /api rewrite). */
export function createApi(
  fetchFn: typeof fetch = fetch,
  baseUrl: string = publicEnv.PUBLIC_API_BASE_URL ?? ''
) {
  const request = createClient(fetchFn, baseUrl);
  const page = (p: number, limit = 20) => ({ page: p, limit });
  return {
    search: (q: string, p = 1) => request<SearchResponse>('/search', { query: { q, page: p, limit: 10 } }),
    stats: () => request<Stats>('/stats'),
    sites: {
      list: (p = 1, limit = 20) => request<Paged<Site>>('/sites', { query: page(p, limit) }),
      create: (body: { title: string; main_url: string; description: string; tags: string[] }) =>
        request<Site>('/sites', { method: 'POST', body }),
      update: (id: number, body: Partial<{ title: string; main_url: string; description: string; tags: string[] }>) =>
        request<Site>(`/sites/${id}`, { method: 'PATCH', body }),
      remove: (id: number) => request<void>(`/sites/${id}`, { method: 'DELETE' })
    },
    urls: {
      list: (p = 1, siteId?: number) =>
        request<Paged<PageRecord>>('/urls', { query: { ...page(p), site_id: siteId } }),
      create: (body: { site_id: number; url: string; title: string; description: string; text: string }) =>
        request<PageRecord>('/urls', { method: 'POST', body }),
      remove: (id: number) => request<void>(`/urls/${id}`, { method: 'DELETE' })
    },
    tags: {
      list: (p = 1) => request<Paged<Tag>>('/tags', { query: page(p, 50) }),
      create: (title: string) => request<Tag>('/tags', { method: 'POST', body: { title } }),
      rename: (id: number, title: string) => request<Tag>(`/tags/${id}`, { method: 'PATCH', body: { title } }),
      remove: (id: number) => request<void>(`/tags/${id}`, { method: 'DELETE' })
    },
    crawl: {
      submit: (body: { url: string; max_pages: number; max_depth: number }) =>
        request<CrawlJob>('/crawl', { method: 'POST', body }),
      jobs: (p = 1) => request<Paged<CrawlJob>>('/crawl/jobs', { query: page(p, 10) })
    }
  };
}
export type Api = ReturnType<typeof createApi>;
