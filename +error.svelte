<script lang="ts">
  import { page } from '$app/state';
</script>

<svelte:head><title>{page.status} – Lookup</title></svelte:head>
<h1 class="font-display text-3xl">{page.status}</h1>
<p class="mt-2 text-muted">{page.error?.message ?? 'Something went wrong.'}</p>
<p class="mt-6"><a class="btn" href="/">Back to search</a></p>
