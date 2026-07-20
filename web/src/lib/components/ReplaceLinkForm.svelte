<script lang="ts">
import { goto } from "$app/navigation";
import { ApiError, api } from "$lib/api";
import type { ReplaceLinkRequest } from "$lib/types";

type Props = {
  channelId: number;
  onSubmit?: (response: { job_id: number }) => void;
};

const { channelId, onSubmit }: Props = $props();

let postUrls = $state("");
let pattern = $state("");
let newLink = $state("");
let error = $state<string | null>(null);
let submitting = $state(false);

const parsedUrls = $derived(
  postUrls
    .split("\n")
    .map((u) => u.trim())
    .filter((u) => u.length > 0),
);
const trimmedPattern = $derived(pattern.trim());
const trimmedNewLink = $derived(newLink.trim());

let patternError = $state<string | null>(null);
$effect(() => {
  if (trimmedPattern.length === 0) {
    patternError = null;
    return;
  }
  try {
    new RegExp(trimmedPattern);
    patternError = null;
  } catch (err) {
    patternError = err instanceof Error ? err.message : "Invalid regex";
  }
});

const canSubmit = $derived(
  !submitting &&
    parsedUrls.length > 0 &&
    trimmedPattern.length > 0 &&
    patternError === null &&
    trimmedNewLink.length > 0,
);

async function handleSubmit(event: Event) {
  event.preventDefault();
  if (!canSubmit) {
    if (parsedUrls.length === 0) {
      error = "Enter at least one post URL";
    } else if (patternError) {
      error = patternError;
    } else {
      error = "Fill all required fields";
    }
    return;
  }
  error = null;
  submitting = true;
  try {
    const payload: ReplaceLinkRequest = {
      post_urls: parsedUrls,
      pattern: trimmedPattern,
      new_link: trimmedNewLink,
    };
    const result = await api.post<{ job_id: number }>(
      `/api/channels/${channelId}/replace-link`,
      payload,
    );
    onSubmit?.(result);
    await goto(`/jobs/${result.job_id}`);
  } catch (err) {
    if (err instanceof ApiError) {
      error = err.message || "Replace-link failed";
    } else {
      error = "Network error";
    }
  } finally {
    submitting = false;
  }
}
</script>

<form class="space-y-4" onsubmit={handleSubmit}>
  <h2 class="text-lg font-semibold text-white">Replace link</h2>

  <div>
    <label for="rl-urls" class="mb-1 block text-xs font-medium text-slate-300">Post URLs</label>
    <textarea
      id="rl-urls"
      rows="4"
      bind:value={postUrls}
      placeholder={"https://t.me/channel/123\nhttps://t.me/c/1234567890/456"}
      class="w-full rounded-md border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
      required
    ></textarea>
    <p class="mt-1 text-xs text-slate-400">
      One URL per line — public (https://t.me/channel/123) or private
      (https://t.me/c/1234567890/456). Parsed: {parsedUrls.length} URL(s).
    </p>
  </div>

  <div>
    <label for="rl-pattern" class="mb-1 block text-xs font-medium text-slate-300">
      Pattern (regex)
    </label>
    <input
      id="rl-pattern"
      type="text"
      bind:value={pattern}
      placeholder="https://old\\.example\\.com"
      class="w-full rounded-md border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
      required
    />
    {#if patternError}
      <p class="mt-1 text-xs text-red-400">Invalid regex: {patternError}</p>
    {:else}
      <p class="mt-1 text-xs text-slate-400">Regex to search for the old link</p>
    {/if}
  </div>

  <div>
    <label for="rl-new-link" class="mb-1 block text-xs font-medium text-slate-300">
      New link
    </label>
    <input
      id="rl-new-link"
      type="text"
      bind:value={newLink}
      placeholder="https://new.example.com"
      class="w-full rounded-md border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
      required
    />
    <p class="mt-1 text-xs text-slate-400">Replacement text for the matched pattern</p>
  </div>

  {#if error}
    <div class="rounded-md border border-red-900 bg-red-950 px-3 py-2 text-sm text-red-200">
      {error}
    </div>
  {/if}

  <div class="flex items-center justify-end gap-2">
    <button
      type="submit"
      disabled={!canSubmit}
      class="rounded-md bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-60"
    >
      {submitting ? "Starting…" : "Run replace-link"}
    </button>
  </div>
</form>