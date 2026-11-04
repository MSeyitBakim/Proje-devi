<script lang="ts">
  import { navigating } from '$app/state';
  import Alert from '$lib/components/Alert.svelte';
  import Icon from '$lib/components/Icon.svelte';
  import Pagination from '$lib/components/Pagination.svelte';
  import type { PageData } from './$types';

  let { data }: { data: PageData } = $props();
  let query = $state(data.q);
  $effect(() => {
    query = data.q;
  });

  const loading = $derived(navigating.to !== null);
  const pageHref = (p: number) => `/?q=${encodeURIComponent(data.q)}&page=${p}`;
</script>

<svelte:head>
  <title>{data.q ? `${data.q} – Lookup` : 'Lookup – search'}</title>
</svelte:head>

<h1 class="font-display text-4xl tracking-tight">Search the indexed web</h1>

<form action="/" method="GET" role="search" class="mt-6 flex gap-2">
  <label for="q" class="sr-only">Search query</label>
  <input
    id="q"
    name="q"
    type="search"
    class="input"
    placeholder="Search…"
    maxlength="200"
    autocomplete="off"
    bind:value={query}
  />
  <button class="btn btn-primary" type="submit"><Icon name="search" /> Search</button>
</form>

<section class="mt-8" aria-busy={loading} aria-live="polite">
  {#if data.error}
    <Alert message={data.error} />
  {:else if !data.q}
    <p class="text-muted">Enter a query to search the pages indexed by this instance.</p>
  {:else if data.response}
    <p class="text-sm text-muted" role="status">
      {data.response.total}
      {data.response.total === 1 ? 'result' : 'results'} for “{data.q}”
    </p>

    {#if data.response.results.length === 0}
      <p class="mt-6">
        No pages matched. Try fewer or different words, or add the site in the
        <a class="underline" href="/admin/sites">admin area</a> and crawl it.
      </p>
    {:else}
      <ol class="mt-4 space-y-6" class:opacity-60={loading}>
        {#each data.response.results as result (result.url)}
          <li>
            <article>
              <p class="text-sm text-muted">{result.site.base_domain}</p>
              <h2 class="font-display text-xl leading-snug">
                <a class="underline-offset-4 hover:underline" href={result.url} rel="noopener noreferrer"
                  >{result.title || result.url}</a
                >
              </h2>
              <p class="mt-1 text-sm">{result.snippet || result.description}</p>
              {#if result.site.tags.length}
                <ul class="mt-2 flex flex-wrap gap-1.5" aria-label="Site tags">
                  {#each result.site.tags as tag (tag)}
                    <li class="rounded-full border border-line px-2 py-0.5 text-xs text-muted">{tag}</li>
                  {/each}
                </ul>
              {/if}
            </article>
          </li>
        {/each}
      </ol>
      <Pagination page={data.page} total={data.response.total} limit={data.response.limit} href={pageHref} />
    {/if}
  {/if}
</section>
