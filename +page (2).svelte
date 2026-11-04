<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { createApi } from '$lib/api';
  import { errorMessage } from '$lib/api/client';
  import type { CrawlJob, Stats } from '$lib/api/types';
  import Alert from '$lib/components/Alert.svelte';

  const api = createApi();
  let jobs = $state<CrawlJob[]>([]);
  let stats = $state<Stats | null>(null);
  let error = $state('');
  let url = $state('');
  let maxPages = $state(20);
  let maxDepth = $state(1);
  let submitting = $state(false);
  let timer: ReturnType<typeof setInterval> | undefined;

  const active = $derived(jobs.some((j) => j.status === 'queued' || j.status === 'running'));

  async function refresh() {
    try {
      [jobs, stats] = await Promise.all([api.crawl.jobs(1).then((r) => r.items), api.stats()]);
    } catch (e) {
      error = errorMessage(e);
    }
  }

  onMount(() => {
    refresh();
    timer = setInterval(() => {
      if (active && !document.hidden) refresh();
    }, 3000);
  });
  onDestroy(() => clearInterval(timer));

  async function submit() {
    submitting = true;
    error = '';
    try {
      await api.crawl.submit({ url: url.trim(), max_pages: maxPages, max_depth: maxDepth });
      url = '';
      await refresh();
    } catch (e) {
      error = errorMessage(e);
    } finally {
      submitting = false;
    }
  }
</script>

<svelte:head><title>Crawl – Admin – Lookup</title></svelte:head>

<h2 class="font-display text-2xl">Crawl</h2>
<p class="mt-1 text-sm text-muted">
  Jobs are queued here and executed by the worker process (<code>python -m app.worker</code>). robots.txt is respected.
</p>

<form class="mt-4 grid gap-3 sm:grid-cols-[1fr_7rem_7rem_auto] sm:items-end" onsubmit={(e) => (e.preventDefault(), submit())}>
  <div><label class="label" for="c-url">Start URL</label><input id="c-url" class="input" type="url" required placeholder="https://example.com" bind:value={url} /></div>
  <div><label class="label" for="c-pages">Max pages</label><input id="c-pages" class="input" type="number" min="1" max="500" required bind:value={maxPages} /></div>
  <div><label class="label" for="c-depth">Max depth</label><input id="c-depth" class="input" type="number" min="0" max="5" required bind:value={maxDepth} /></div>
  <button class="btn btn-primary" type="submit" disabled={submitting}>{submitting ? 'Queuing…' : 'Start crawl'}</button>
</form>

<div class="mt-6 space-y-4">
  {#if error}<Alert message={error} />{/if}

  {#if stats}
    <p class="text-sm text-muted">
      {stats.sites} sites · {stats.pages} pages · {stats.terms} terms · queue: {stats.queue.pending} pending,
      {stats.queue.in_progress} in progress
    </p>
  {/if}

  {#if jobs.length === 0}
    <p class="text-muted">No crawl jobs yet.</p>
  {:else}
    <div class="table-wrap" aria-live="polite">
      <table class="table">
        <caption class="sr-only">Crawl jobs</caption>
        <thead><tr><th scope="col">Seed</th><th scope="col">Status</th><th scope="col">Crawled</th><th scope="col">Failed</th><th scope="col">Pending</th></tr></thead>
        <tbody>
          {#each jobs as job (job.id)}
            <tr>
              <td class="max-w-xs break-all">{job.seed_url}</td>
              <td>
                <span class="font-medium">{job.status}</span>
                {#if job.error}<span class="block text-xs text-danger">{job.error}</span>{/if}
              </td>
              <td>{job.pages_crawled} / {job.max_pages}</td>
              <td>{job.pages_failed}</td>
              <td>{job.urls_pending + job.urls_in_progress}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>
