import { createApi } from '$lib/api';
import { errorMessage } from '$lib/api/client';
import type { SearchResponse } from '$lib/api/types';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ url, fetch }) => {
  const q = (url.searchParams.get('q') ?? '').trim();
  const page = Math.max(1, Math.floor(Number(url.searchParams.get('page'))) || 1);
  if (!q) return { q, page, response: null as SearchResponse | null, error: null as string | null };
  try {
    return { q, page, response: await createApi(fetch).search(q, page), error: null as string | null };
  } catch (error) {
    return { q, page, response: null as SearchResponse | null, error: errorMessage(error) };
  }
};
