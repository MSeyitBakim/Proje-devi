<script lang="ts">
  import { page } from '$app/state';
  import type { Snippet } from 'svelte';

  let { children }: { children: Snippet } = $props();
  const links = [
    ['/admin/sites', 'Siteler'],
    ['/admin/urls', 'URL\'ler'],
    ['/admin/tags', 'Etiketler'],
    ['/admin/crawl', 'Tarama']
  ];
</script>

<h1 class="font-display text-3xl">Yönetim paneli</h1>
<nav aria-label="Admin sections" class="mt-4 flex flex-wrap gap-2 border-b border-line pb-3">
  {#each links as [href, label] (href)}
    <a
      {href}
      class="btn {page.url.pathname === href ? 'btn-primary' : ''}"
      aria-current={page.url.pathname === href ? 'page' : undefined}>{label}</a
    >
  {/each}
</nav>
<div class="mt-6">{@render children()}</div>
<p class="mt-8 text-xs text-muted">
  Bu arayüzün kimlik doğrulaması yoktur. Bunu veya API'yi güvenilmeyen ağlara açmayın.
</p>
