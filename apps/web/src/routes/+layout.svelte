<script lang="ts">
  import '../app.css';
  import { page } from '$app/state';
  import type { Snippet } from 'svelte';

  let { children }: { children: Snippet } = $props();
  const inAdmin = $derived(page.url.pathname.startsWith('/admin'));
</script>

<a
  href="#main"
  class="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-50 focus:rounded-md focus:bg-surface focus:px-3 focus:py-2"
  >Skip to content</a
>

<header class="border-b border-line">
  <div class="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-3">
    <a href="/" class="font-display text-xl tracking-tight">Web</a>
    <nav aria-label="Primary" class="flex gap-4 text-sm">
      <a href="/" aria-current={!inAdmin ? 'page' : undefined} class="underline-offset-4 aria-[current]:underline">Arama</a>
      <a href="/admin/sites" aria-current={inAdmin ? 'page' : undefined} class="underline-offset-4 aria-[current]:underline">Yönetim</a>
    </nav>
  </div>
</header>

<main id="main" class="mx-auto max-w-5xl px-4 py-8">
  {@render children()}
</main>
