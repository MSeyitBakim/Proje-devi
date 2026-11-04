<script lang="ts">
  import { onMount } from 'svelte';
  import { createApi } from '$lib/api';
  import { errorMessage } from '$lib/api/client';
  import type { Tag } from '$lib/api/types';
  import Alert from '$lib/components/Alert.svelte';
  import Dialog from '$lib/components/Dialog.svelte';
  import Icon from '$lib/components/Icon.svelte';

  const api = createApi();
  let tags = $state<Tag[]>([]);
  let loading = $state(true);
  let error = $state('');
  let newTitle = $state('');

  let renaming = $state<Tag | null>(null);
  let renameOpen = $state(false);
  let renameTitle = $state('');
  let renameError = $state('');
  let deleting = $state<Tag | null>(null);
  let deleteOpen = $state(false);

  async function load() {
    loading = true;
    try {
      tags = (await api.tags.list(1)).items;
      error = '';
    } catch (e) {
      error = errorMessage(e);
    } finally {
      loading = false;
    }
  }
  onMount(load);

  async function create() {
    try {
      await api.tags.create(newTitle.trim());
      newTitle = '';
      await load();
    } catch (e) {
      error = errorMessage(e);
    }
  }

  async function rename() {
    if (!renaming) return;
    try {
      await api.tags.rename(renaming.id, renameTitle.trim());
      renameOpen = false;
      await load();
    } catch (e) {
      renameError = errorMessage(e);
    }
  }

  async function remove() {
    if (!deleting) return;
    try {
      await api.tags.remove(deleting.id);
    } catch (e) {
      error = errorMessage(e);
    }
    deleteOpen = false;
    await load();
  }
</script>

<svelte:head><title>Etiketler – Yönetim – Web</title></svelte:head>

<h2 class="font-display text-2xl">Etiketler</h2>

<form class="mt-4 flex items-end gap-2" onsubmit={(e) => (e.preventDefault(), create())}>
  <div class="grow">
    <label class="label" for="new-tag">Yeni etiket</label>
    <input id="new-tag" class="input" required maxlength="50" bind:value={newTitle} />
  </div>
  <button class="btn btn-primary" type="submit"><Icon name="plus" /> Ekle</button>
</form>

<div class="mt-6" aria-busy={loading}>
  {#if error}<Alert message={error} />{/if}
  {#if !loading && !error && tags.length === 0}
    <p class="text-muted">Henüz etiket yok.</p>
  {:else if tags.length}
    <ul class="divide-y divide-line rounded-md border border-line bg-surface">
      {#each tags as tag (tag.id)}
        <li class="flex items-center justify-between gap-3 px-3 py-2">
          <span>{tag.title}</span>
          <span class="flex gap-2">
            <button class="btn" type="button" aria-label="Yeniden adlandır {tag.title}" onclick={() => ((renaming = tag), (renameTitle = tag.title), (renameError = ''), (renameOpen = true))}><Icon name="pencil" /></button>
            <button class="btn btn-danger" type="button" aria-label="Sil {tag.title}" onclick={() => ((deleting = tag), (deleteOpen = true))}><Icon name="trash" /></button>
          </span>
        </li>
      {/each}
    </ul>
  {/if}
</div>

<Dialog bind:open={renameOpen} title="Etiketi yeniden adlandır">
  <form onsubmit={(e) => (e.preventDefault(), rename())} class="space-y-4">
    {#if renameError}<Alert message={renameError} />{/if}
    <div><label class="label" for="rename">Başlık</label><input id="rename" class="input" required maxlength="50" bind:value={renameTitle} /></div>
    <div class="flex justify-end gap-2">
      <button class="btn" type="button" onclick={() => (renameOpen = false)}>İptal</button>
      <button class="btn btn-primary" type="submit">Kaydet</button>
    </div>
  </form>
</Dialog>

<Dialog bind:open={deleteOpen} title="Etiketi silmek ister misiniz?">
  <p><strong>{deleting?.title}</strong> etiketini kullanan tüm sitelerden kaldırsın mı?</p>
  <div class="mt-5 flex justify-end gap-2">
    <button class="btn" type="button" onclick={() => (deleteOpen = false)}>İptal</button>
    <button class="btn btn-danger" type="button" onclick={remove}>Etiketi sil</button>
  </div>
</Dialog>
