<script lang="ts">
  import type { Snippet } from 'svelte';
  import Icon from './Icon.svelte';

  let {
    open = $bindable(false),
    title,
    children
  }: { open: boolean; title: string; children: Snippet } = $props();

  let element: HTMLDialogElement;
  const titleId = `dialog-${Math.random().toString(36).slice(2, 9)}`;

  // Native <dialog>: focus trapping, Esc to close, and inert background come from the browser.
  $effect(() => {
    if (open && !element.open) element.showModal();
    if (!open && element.open) element.close();
  });
</script>

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_noninteractive_element_interactions -->
<!-- Backdrop click closes; keyboard users close with Esc (native) or the Close button. -->
<dialog
  bind:this={element}
  aria-labelledby={titleId}
  onclose={() => (open = false)}
  onclick={(event) => event.target === element && (open = false)}
  class="m-auto w-[min(34rem,calc(100vw-2rem))] rounded-lg border border-line bg-surface p-0 text-ink backdrop:bg-black/50"
>
  <div class="p-5">
    <div class="mb-4 flex items-start justify-between gap-4">
      <h2 id={titleId} class="font-display text-xl">{title}</h2>
      <button class="btn" type="button" aria-label="Close dialog" onclick={() => (open = false)}>
        <Icon name="x" />
      </button>
    </div>
    {#if open}{@render children()}{/if}
  </div>
</dialog>
