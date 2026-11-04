<script lang="ts">
  import { pageCount, pageWindow } from '$lib/pagination';

  let {
    page,
    total,
    limit,
    href,
    onselect
  }: {
    page: number;
    total: number;
    limit: number;
    href?: (page: number) => string;
    onselect?: (page: number) => void;
  } = $props();

  const last = $derived(pageCount(total, limit));
  const items = $derived(pageWindow(page, last));
</script>

{#if last > 1}
  <nav aria-label="Pagination" class="mt-6 flex flex-wrap items-center gap-1.5">
    {#each items as item, index (index)}
      {#if item === '…'}
        <span class="px-1 text-muted" aria-hidden="true">…</span>
      {:else if href}
        <a
          class="btn min-w-10 {item === page ? 'btn-primary' : ''}"
          href={href(item)}
          aria-current={item === page ? 'page' : undefined}
          aria-label="Page {item}">{item}</a
        >
      {:else}
        <button
          type="button"
          class="btn min-w-10 {item === page ? 'btn-primary' : ''}"
          aria-current={item === page ? 'page' : undefined}
          aria-label="Page {item}"
          onclick={() => onselect?.(item)}>{item}</button
        >
      {/if}
    {/each}
  </nav>
{/if}
