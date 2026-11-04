<script lang="ts">
  import { navigating } from '$app/state';
  import { untrack } from 'svelte';
  import Alert from '$lib/components/Alert.svelte';
  import Icon from '$lib/components/Icon.svelte';
  import Pagination from '$lib/components/Pagination.svelte';
  import type { PageData } from './$types';

  let { data }: { data: PageData } = $props();
  let query = $state(untrack(() => data.q));
  $effect(() => {
    query = data.q;
  });

  const loading = $derived(navigating.to !== null);
  const pageHref = (p: number) => `/?q=${encodeURIComponent(data.q)}&page=${p}`;
</script>

<svelte:head>
  <title>{data.q ? `${data.q} – Web` : 'Web – arama'}</title>
</svelte:head>

<h1 class="font-display text-4xl tracking-tight">İndekslenmiş web üzerinde ara</h1>

<form action="/" method="GET" role="search" class="mt-6 flex gap-2">
  <label for="q" class="sr-only">Arama metni</label>
  <input
    id="q"
    name="q"
    type="search"
    class="input"
    placeholder="Bir şeyler yazın..."
    maxlength="200"
    autocomplete="off"
    bind:value={query}
  />
  <button class="btn btn-primary" type="submit"><Icon name="search" /> Ara</button>
</form>

<section class="mt-8" aria-busy={loading} aria-live="polite">
  {#if data.error}
    <Alert message={data.error} />
  {:else if !data.q}
    <p class="text-muted">Bu örnekte indekslenmiş sayfalarda arama yapmak için bir şeyler yazın.</p>
  {:else if data.response}
    <p class="text-sm text-muted" role="status">
      “{data.q}” için {data.response.total} sonuç bulundu
    </p>

    {#if data.response.results.length === 0}
      <p class="mt-6">
        Hiçbir sayfa eşleşmedi. Daha kısa ya da farklı kelimeler deneyin; isterseniz siteyi
        <a class="underline" href="/admin/sites">yönetim bölümüne</a> ekleyip taratabilirsiniz.
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
