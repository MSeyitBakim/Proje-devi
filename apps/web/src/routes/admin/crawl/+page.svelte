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

<svelte:head><title>Tarama – Yönetim – Web</title></svelte:head>

<h2 class="font-display text-2xl">Tarama</h2>
<p class="mt-1 text-sm text-muted">
  Görevler burada sıraya alınır ve arka plan işçisi tarafından çalıştırılır (<code>python -m app.worker</code>). robots.txt kurallarına uyulur.
</p>

<form class="mt-4 grid gap-3 sm:grid-cols-[1fr_7rem_7rem_auto] sm:items-end" onsubmit={(e) => (e.preventDefault(), submit())}>
  <div><label class="label" for="c-url">Başlangıç URL'si</label><input id="c-url" class="input" type="url" required placeholder="https://example.com" bind:value={url} /></div>
  <div><label class="label" for="c-pages">En fazla sayfa</label><input id="c-pages" class="input" type="number" min="1" max="500" required bind:value={maxPages} /></div>
  <div><label class="label" for="c-depth">En fazla derinlik</label><input id="c-depth" class="input" type="number" min="0" max="5" required bind:value={maxDepth} /></div>
  <button class="btn btn-primary" type="submit" disabled={submitting}>{submitting ? 'Sıraya alınıyor...' : 'Tarama başlat'}</button>
</form>

<div class="mt-6 space-y-4">
  {#if error}<Alert message={error} />{/if}

  {#if stats}
    <p class="text-sm text-muted">
      {stats.sites} site · {stats.pages} sayfa · {stats.terms} terim · kuyruk: {stats.queue.pending} bekliyor,
      {stats.queue.in_progress} işleniyor
    </p>
  {/if}

  {#if jobs.length === 0}
    <p class="text-muted">Henüz tarama işi yok.</p>
  {:else}
    <div class="table-wrap" aria-live="polite">
      <table class="table">
        <caption class="sr-only">Tarama işleri</caption>
        <thead><tr><th scope="col">Tohum</th><th scope="col">Durum</th><th scope="col">Tarandı</th><th scope="col">Başarısız</th><th scope="col">Bekleyen</th></tr></thead>
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
