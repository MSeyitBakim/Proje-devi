import { env } from '$env/dynamic/private';
import { createApi } from '$lib/api';
import { errorMessage } from '$lib/api/client';
import type { SearchResponse } from '$lib/api/types';
import type { PageServerLoad } from './$types';

// Runs on the server (also for client-side navigations, via SvelteKit's data requests).
// On Vercel, BACKEND_URL is injected by the service binding and points at the internal
// backend service. Locally it is unset, so the call goes through the Vite /api proxy.
export const load: PageServerLoad = async ({ url, fetch }) => {
  const q = (url.searchParams.get('q') ?? '').trim();
  const page = Math.max(1, Math.floor(Number(url.searchParams.get('page'))) || 1);
  if (!q) return { q, page, response: null as SearchResponse | null, error: null as string | null };
  try {
    const api = createApi(fetch, env.BACKEND_URL || undefined);
    return { q, page, response: await api.search(q, page), error: null as string | null };
  } catch (error) {
    return { q, page, response: null as SearchResponse | null, error: errorMessage(error) };
  }
};
