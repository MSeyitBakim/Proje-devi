<script lang="ts">
  let { message, tone = 'error' }: { message: string; tone?: 'error' | 'info' } = $props();
</script>

<p
  role={tone === 'error' ? 'alert' : 'status'}
  class="rounded-md border px-3 py-2 text-sm {tone === 'error'
    ? 'border-danger text-danger'
    : 'border-line text-muted'}"
>
  {message}
</p>
