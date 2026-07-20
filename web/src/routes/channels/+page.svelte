<script lang="ts">
import { ApiError, api } from "$lib/api";
import ChannelForm from "$lib/components/ChannelForm.svelte";
import type { Channel } from "$lib/types";

type Props = { data: { channels: Channel[]; total: number } };
const { data }: Props = $props();

let error = $state<string | null>(null);
let busy = $state(false);
let localRefresh = $state<Channel[] | null>(null);
let showForm = $state(false);

const channels = $derived.by<Channel[]>(() => localRefresh ?? data.channels);

async function reload() {
  try {
    const data = await api.get<{ channels: Channel[]; total: number }>("/api/channels");
    localRefresh = data.channels;
  } catch (err) {
    error = err instanceof ApiError ? err.message : "Failed to reload";
  }
}

async function deleteChannel(channel: Channel) {
  if (!confirm(`Delete channel "${channel.title}"?`)) return;
  busy = true;
  try {
    await api.del(`/api/channels/${channel.id}`);
    await reload();
  } catch (err) {
    error = err instanceof ApiError ? err.message : "Delete failed";
  } finally {
    busy = false;
  }
}

function handleSaved(_channel: Channel) {
  showForm = false;
  void reload();
}
</script>

<div class="space-y-4">
  <div class="flex flex-wrap items-center justify-between gap-3">
    <h1 class="text-2xl font-semibold text-white">Channels</h1>
    <button
      type="button"
      onclick={() => (showForm = !showForm)}
      class="rounded-md bg-brand-600 px-3 py-2 text-sm font-semibold text-white hover:bg-brand-700"
    >
      {showForm ? "Close" : "Add channel"}
    </button>
  </div>

  {#if showForm}
    <div class="rounded-lg border border-slate-800 bg-slate-900 p-4">
      <ChannelForm onSaved={handleSaved} onCancel={() => (showForm = false)} />
    </div>
  {/if}

  {#if error}
    <div class="rounded-md border border-red-900 bg-red-950 px-3 py-2 text-sm text-red-200">
      {error}
    </div>
  {/if}

  <div class="overflow-x-auto rounded-lg border border-slate-800 bg-slate-900">
    <table class="min-w-full divide-y divide-slate-800 text-sm">
      <thead class="bg-slate-900 text-xs text-slate-400">
        <tr>
          <th class="px-3 py-2 text-left font-medium">Title</th>
          <th class="px-3 py-2 text-left font-medium">Telegram ID</th>
          <th class="px-3 py-2 text-left font-medium">Username</th>
          <th class="px-3 py-2 text-left font-medium">Active</th>
          <th class="px-3 py-2 text-right font-medium">Actions</th>
        </tr>
      </thead>
      <tbody class="divide-y divide-slate-800">
        {#each channels as ch (ch.id)}
          <tr class="hover:bg-slate-800/40">
            <td class="px-3 py-2 font-medium text-white">
              <a href={`/channels/${ch.id}`} class="hover:text-brand-400">{ch.title}</a>
            </td>
            <td class="px-3 py-2 text-slate-300">{ch.telegram_id}</td>
            <td class="px-3 py-2 text-slate-300">{ch.username ?? "—"}</td>
            <td class="px-3 py-2">
              {#if ch.is_active}
                <span class="rounded bg-emerald-900/60 px-2 py-0.5 text-xs text-emerald-200">
                  active
                </span>
              {:else}
                <span class="rounded bg-slate-800 px-2 py-0.5 text-xs text-slate-400">
                  inactive
                </span>
              {/if}
            </td>
            <td class="px-3 py-2 text-right">
              <button
                type="button"
                onclick={() => deleteChannel(ch)}
                disabled={busy}
                class="rounded-md bg-red-900 px-2 py-1 text-xs text-red-100 hover:bg-red-800 disabled:opacity-60"
              >
                Delete
              </button>
            </td>
          </tr>
        {:else}
          <tr>
            <td colspan="5" class="px-3 py-8 text-center text-slate-400">No channels</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
</div>