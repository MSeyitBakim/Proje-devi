export interface Paged<T> {
  items: T[];
  total: number;
  page: number;
  limit: number;
}
export interface Site {
  id: number;
  title: string;
  main_url: string;
  base_domain: string;
  description: string;
  tags: string[];
  created_at: string;
  updated_at: string;
}
export interface Tag {
  id: number;
  title: string;
  created_at: string;
}
export interface PageRecord {
  id: number;
  site_id: number;
  url: string;
  title: string;
  description: string;
  status_code: number | null;
  doc_length: number;
  crawled_at: string | null;
}
export interface SearchResult {
  url: string;
  title: string;
  description: string;
  snippet: string;
  score: number;
  site: { id: number; title: string; base_domain: string; tags: string[] };
}
export interface SearchResponse {
  query: string;
  results: SearchResult[];
  total: number;
  page: number;
  limit: number;
}
export type JobStatus = 'queued' | 'running' | 'completed' | 'failed';
export interface CrawlJob {
  id: number;
  seed_url: string;
  status: JobStatus;
  max_pages: number;
  max_depth: number;
  pages_crawled: number;
  pages_failed: number;
  urls_pending: number;
  urls_in_progress: number;
  urls_done: number;
  urls_failed: number;
  error: string | null;
  created_at: string;
}
export interface Stats {
  sites: number;
  pages: number;
  terms: number;
  queue: Record<string, number>;
}
