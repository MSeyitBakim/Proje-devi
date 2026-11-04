<script lang="ts">
  import { onMount } from 'svelte';
  import { createApi } from '$lib/api';
  import { errorMessage } from '$lib/api/client';
  import type { Site } from '$lib/api/types';
  import Alert from '$lib/components/Alert.svelte';
  import Dialog from '$lib/components/Dialog.svelte';
  import Icon from '$lib/components/Icon.svelte';
  import Pagination from '$lib/components/Pagination.svelte';

  const api = createApi();
  const limit = 20;
  let sites = $state<Site[]>([]);
  let total = $state(0);
  let page = $state(1);
  let loading = $state(true);
  let error = $state('');

  let formOpen = $state(false);
  let editing = $state<Site | null>(null);
  let form = $state({ title: '', main_url: '', description: '', tags: '' });
  let formError = $state('');
  let saving = $state(false);
  let deleting = $state<Site | null>(null);
  let deleteOpen = $state(false);

  async function load() {
    loading = true;
    error = '';
    try {
      const result = await api.sites.list(page, limit);
      sites = result.items;
      total = result.total;
    } catch (e) {
      error = errorMessage(e);
    } finally {
      loading = false;
    }
  }
  onMount(load);

  function openForm(site: Site | null) {
    editing = site;
    form = site
      ? { title: site.title, main_url: site.main_url, description: site.description, tags: site.tags.join(', ') }
      : { title: '', main_url: '', description: '', tags: '' };
    formError = '';
    formOpen = true;
  }

  async function save() {
    saving = true;
    formError = '';
    const body = {
      title: form.title.trim(),
      main_url: form.main_url.trim(),
      description: form.description.trim(),
      tags: form.tags.split(',').map((t) => t.trim()).filter(Boolean)
    };
    try {
      if (editing) await api.sites.update(editing.id, body);
      else await api.sites.create(body);
      formOpen = false;
      await load();
    } catch (e) {
      formError = errorMessage(e);
    } finally {
      saving = false;
    }
  }

  async function confirmDelete() {
    if (!deleting) return;
    try {
      await api.sites.remove(deleting.id);
      deleteOpen = false;
      if (sites.length === 1 && page > 1) page -= 1;
      await load();
    } catch (e) {
      error = errorMessage(e);
      deleteOpen = false;
    }
  }
</script>

<svelte:head><title>Siteler – Yönetim – Web</title></svelte:head>

<div class="flex items-center justify-between gap-3">
  <h2 class="font-display text-2xl">Siteler</h2>
  <button class="btn btn-primary" type="button" onclick={() => openForm(null)}><Icon name="plus" /> Site ekle</button>
</div>

<div class="mt-4" aria-busy={loading}>
  {#if error}<Alert message={error} />{/if}
  {#if !loading && !error && sites.length === 0}
    <p class="text-muted">Henüz site yok. Bir tane ekleyin, ardından Tarama sekmesinden taramayı başlatın.</p>
  {:else if sites.length}
    <div class="table-wrap">
      <table class="table">
        <caption class="sr-only">Kayıtlı siteler</caption>
        <thead><tr><th scope="col">Başlık</th><th scope="col">Alan adı</th><th scope="col">Etiketler</th><th scope="col"><span class="sr-only">İşlemler</span></th></tr></thead>
        <tbody>
          {#each sites as site (site.id)}
            <tr>
              <td>{site.title}</td>
              <td><a class="underline" href={site.main_url} rel="noopener noreferrer">{site.base_domain}</a></td>
              <td>{site.tags.join(', ') || '—'}</td>
              <td class="whitespace-nowrap text-right">
                <button class="btn" type="button" aria-label="Düzenle {site.title}" onclick={() => openForm(site)}><Icon name="pencil" /></button>
                <button class="btn btn-danger" type="button" aria-label="Sil {site.title}" onclick={() => ((deleting = site), (deleteOpen = true))}><Icon name="trash" /></button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
    <Pagination {page} {total} {limit} onselect={(p) => ((page = p), load())} />
  {/if}
</div>

<Dialog bind:open={formOpen} title={editing ? 'Site bilgilerini düzenle' : 'Site ekle'}>
  <form onsubmit={(e) => (e.preventDefault(), save())} class="space-y-4">
    {#if formError}<Alert message={formError} />{/if}
    <div><label class="label" for="s-title">Başlık</label><input id="s-title" class="input" required maxlength="200" bind:value={form.title} /></div>
    <div><label class="label" for="s-url">Ana URL</label><input id="s-url" class="input" type="url" required placeholder="https://example.com" bind:value={form.main_url} /></div>
    <div><label class="label" for="s-desc">Açıklama</label><textarea id="s-desc" class="input" rows="3" maxlength="2000" bind:value={form.description}></textarea></div>
    <div><label class="label" for="s-tags">Etiketler</label><input id="s-tags" class="input" placeholder="virgülle ayrılmış" bind:value={form.tags} /></div>
    <div class="flex justify-end gap-2">
      <button class="btn" type="button" onclick={() => (formOpen = false)}>İptal</button>
      <button class="btn btn-primary" type="submit" disabled={saving}>{saving ? 'Kaydediliyor…' : 'Kaydet'}</button>
    </div>
  </form>
</Dialog>

<Dialog bind:open={deleteOpen} title="Siteyi silmek istiyor musunuz?">
  <p>
    Bu işlem <strong>{deleting?.title}</strong> ve ona ait tüm indekslenmiş sayfaları kaldırır. Bu işlem geri alınamaz.
  </p>
  <div class="mt-5 flex justify-end gap-2">
    <button class="btn" type="button" onclick={() => (deleteOpen = false)}>İptal</button>
    <button class="btn btn-danger" type="button" onclick={confirmDelete}>Siteyi sil</button>
  </div>
</Dialog>
