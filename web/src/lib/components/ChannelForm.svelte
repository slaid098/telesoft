<script lang="ts">
import { ApiError, api } from "$lib/api";
import type { Channel, ChannelCreate } from "$lib/types";

type Props = {
  onSaved?: (channel: Channel) => void;
  onCancel?: () => void;
};

const { onSaved, onCancel }: Props = $props();

let telegramId = $state("");
let title = $state("");
let username = $state("");
let error = $state<string | null>(null);
let saving = $state(false);

const trimmedTitle = $derived(title.trim());
const trimmedUsername = $derived(username.trim());
const telegramIdNum = $derived(Number(telegramId));
const hasTelegramId = $derived(
  telegramId.trim().length > 0 && Number.isFinite(telegramIdNum) && telegramIdNum !== 0,
);
const canSubmit = $derived(trimmedTitle.length > 0 && hasTelegramId && !saving);

async function handleSubmit(event: Event) {
  event.preventDefault();
  if (!canSubmit) {
    error = "Enter a valid telegram_id and title";
    return;
  }
  error = null;
  saving = true;
  try {
    const payload: ChannelCreate = {
      telegram_id: telegramIdNum,
      title: trimmedTitle,
      ...(trimmedUsername ? { username: trimmedUsername } : {}),
    };
    const saved = await api.post<Channel>("/api/channels", payload);
    onSaved?.(saved);
  } catch (err) {
    if (err instanceof ApiError) {
      error = err.message || "Save failed";
    } else {
      error = "Network error";
    }
  } finally {
    saving = false;
  }
}
</script>

<form class="space-y-4" onsubmit={handleSubmit}>
  <h2 class="text-lg font-semibold text-white">New channel</h2>

  <div>
    <label for="ch-telegram-id" class="mb-1 block text-xs font-medium text-slate-300">
      Telegram ID
    </label>
    <input
      id="ch-telegram-id"
      type="number"
      bind:value={telegramId}
      placeholder="-1001234567890"
      class="w-full rounded-md border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
      required
    />
    <p class="mt-1 text-xs text-slate-400">
      Channel id with -100 prefix (e.g. -1001234567890)
    </p>
  </div>

  <div>
    <label for="ch-title" class="mb-1 block text-xs font-medium text-slate-300">Title</label>
    <input
      id="ch-title"
      type="text"
      maxlength="200"
      bind:value={title}
      class="w-full rounded-md border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
      required
    />
  </div>

  <div>
    <label for="ch-username" class="mb-1 block text-xs font-medium text-slate-300">
      Username (optional)
    </label>
    <input
      id="ch-username"
      type="text"
      bind:value={username}
      placeholder="mychannel"
      class="w-full rounded-md border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
    />
    <p class="mt-1 text-xs text-slate-400">Public channel @username without @</p>
  </div>

  {#if error}
    <div class="rounded-md border border-red-900 bg-red-950 px-3 py-2 text-sm text-red-200">
      {error}
    </div>
  {/if}

  <div class="flex items-center justify-end gap-2">
    <button
      type="button"
      onclick={onCancel}
      disabled={saving}
      class="rounded-md border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-200 hover:bg-slate-700 disabled:opacity-60"
    >
      Cancel
    </button>
    <button
      type="submit"
      disabled={!canSubmit}
      class="rounded-md bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-60"
    >
      {saving ? "Saving…" : "Save"}
    </button>
  </div>
</form>