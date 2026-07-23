<script lang="ts">
import { ApiError, api, listChannels, toggleChannelActive } from "$lib/api";
import ActionMenu from "$lib/components/ActionMenu.svelte";
import ChannelForm from "$lib/components/ChannelForm.svelte";
import EditChannelModal from "$lib/components/EditChannelModal.svelte";
import ReplaceLinkModal from "$lib/components/ReplaceLinkModal.svelte";
import type { Channel } from "$lib/types";

type Props = { data: { channels: Channel[]; total: number } };
const { data }: Props = $props();

let error = $state<string | null>(null);
let busy = $state(false);
let localRefresh = $state<Channel[] | null>(null);
let showForm = $state(false);
let channelFilter = $state<"active" | "all">("active");
let replaceChannel = $state<Channel | null>(null);
let editChannel = $state<Channel | null>(null);

const channels = $derived.by<Channel[]>(() => localRefresh ?? data.channels);

async function reload() {
  try {
    const resp = await listChannels(channelFilter === "all");
    localRefresh = resp.channels;
  } catch (err) {
    error = err instanceof ApiError ? err.message : "Не удалось перезагрузить";
  }
}

async function deleteChannel(channel: Channel) {
  if (!confirm(`Удалить канал «${channel.title}»?`)) return;
  busy = true;
  error = null;
  try {
    await api.del(`/api/channels/${channel.id}`);
    await reload();
  } catch (err) {
    error = err instanceof ApiError ? err.message : "Не удалось удалить";
  } finally {
    busy = false;
  }
}

async function handleToggleActive(channel: Channel) {
  busy = true;
  error = null;
  try {
    await toggleChannelActive(channel.id, !channel.is_active);
    await reload();
  } catch (err) {
    error = err instanceof ApiError ? err.message : "Не удалось изменить статус";
  } finally {
    busy = false;
  }
}

function handleSaved(_channel: Channel) {
  showForm = false;
  editChannel = null;
  void reload();
}

async function onFilterChange() {
  await reload();
}
</script>

<div class="space-y-4">
  <div class="flex flex-wrap items-center justify-between gap-3">
    <h1 class="text-2xl font-semibold text-white">Каналы</h1>
    <div class="flex flex-wrap items-center gap-2">
      {#if !showForm}
        <div class="flex items-center gap-2">
          <label for="channel-filter" class="text-xs text-slate-400">Фильтр</label>
          <select
            id="channel-filter"
            bind:value={channelFilter}
            onchange={onFilterChange}
            class="rounded-md border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          >
            <option value="active">Только активные</option>
            <option value="all">Все каналы</option>
          </select>
        </div>
      {/if}
      <button
        type="button"
        onclick={() => (showForm = !showForm)}
        class="rounded-md bg-brand-600 px-3 py-2 text-sm font-semibold text-white hover:bg-brand-700"
      >
        {showForm ? "Закрыть" : "Добавить канал"}
      </button>
    </div>
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

  <div class="hidden overflow-x-auto rounded-lg border border-slate-800 bg-slate-900 sm:block">
    <table class="min-w-full divide-y divide-slate-800 text-sm">
      <thead class="bg-slate-900 text-xs text-slate-400">
        <tr>
          <th class="px-3 py-2 text-left font-medium">Название</th>
          <th class="px-3 py-2 text-left font-medium">Telegram ID</th>
          <th class="px-3 py-2 text-left font-medium">Username</th>
          <th class="px-3 py-2 text-left font-medium">Активен</th>
          <th class="px-3 py-2 text-right font-medium">Действия</th>
        </tr>
      </thead>
      <tbody class="divide-y divide-slate-800">
        {#each channels as ch (ch.id)}
          <tr class={`hover:bg-slate-800/40 ${ch.is_active ? "" : "opacity-60"}`}>
            <td class="px-3 py-2 font-medium text-white">
              <a href={`/channels/${ch.id}`} class="hover:text-brand-400">{ch.title}</a>
            </td>
            <td class="px-3 py-2 text-slate-300">{ch.telegram_id}</td>
            <td class="px-3 py-2 text-slate-300">{ch.username ?? "—"}</td>
            <td class="px-3 py-2">
              {#if ch.is_active}
                <span class="rounded bg-emerald-900/60 px-2 py-0.5 text-xs text-emerald-200">
                  активен
                </span>
              {:else}
                <span class="rounded bg-slate-800 px-2 py-0.5 text-xs text-slate-400">
                  неактивен
                </span>
              {/if}
            </td>
            <td class="px-3 py-2 text-right">
              <ActionMenu
                channel={ch}
                onReplace={() => (replaceChannel = ch)}
                onEdit={() => (editChannel = ch)}
                onToggleActive={() => handleToggleActive(ch)}
                onDelete={() => deleteChannel(ch)}
              />
            </td>
          </tr>
        {:else}
          <tr>
            <td colspan="5" class="px-3 py-8 text-center text-slate-400">Нет каналов</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>

  <div class="space-y-3 sm:hidden">
    {#each channels as ch (ch.id)}
      <div class={`rounded-lg border border-slate-800 bg-slate-900 p-3 ${ch.is_active ? "" : "opacity-60"}`}>
        <div class="flex items-start justify-between gap-2">
          <a
            href={`/channels/${ch.id}`}
            class="font-medium text-white hover:text-brand-400"
          >
            {ch.title}
          </a>
          {#if ch.is_active}
            <span class="rounded bg-emerald-900/60 px-2 py-0.5 text-xs text-emerald-200">
              активен
            </span>
          {:else}
            <span class="rounded bg-slate-800 px-2 py-0.5 text-xs text-slate-400">
              неактивен
            </span>
          {/if}
        </div>
        <dl class="mt-2 space-y-1 text-xs text-slate-300">
          <div class="flex justify-between gap-2">
            <dt class="text-slate-400">Telegram ID</dt>
            <dd>{ch.telegram_id}</dd>
          </div>
          <div class="flex justify-between gap-2">
            <dt class="text-slate-400">Username</dt>
            <dd>{ch.username ?? "—"}</dd>
          </div>
        </dl>
        <div class="mt-3 flex items-center justify-end gap-2">
          <ActionMenu
            channel={ch}
            onReplace={() => (replaceChannel = ch)}
            onEdit={() => (editChannel = ch)}
            onToggleActive={() => handleToggleActive(ch)}
            onDelete={() => deleteChannel(ch)}
          />
        </div>
      </div>
    {:else}
      <div class="rounded-lg border border-slate-800 bg-slate-900 p-4 text-center text-sm text-slate-400">
        Нет каналов
      </div>
    {/each}
  </div>
</div>

{#if replaceChannel}
  <ReplaceLinkModal channelId={replaceChannel.id} onClose={() => (replaceChannel = null)} />
{/if}

{#if editChannel}
  <EditChannelModal
    channel={editChannel}
    onSaved={handleSaved}
    onClose={() => (editChannel = null)}
  />
{/if}