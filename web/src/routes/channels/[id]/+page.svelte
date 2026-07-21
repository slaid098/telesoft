<script lang="ts">
import PreviewModal from "$lib/components/PreviewModal.svelte";
import ReplaceLinkForm from "$lib/components/ReplaceLinkForm.svelte";
import type { Channel, Job, PreviewResponse } from "$lib/types";
import { JOB_STATUS_LABELS } from "$lib/types";

type Props = { data: { channel: Channel; recentJobs: Job[] } };
const { data }: Props = $props();

const channel = $derived(data.channel);
const recentJobs = $derived(data.recentJobs);

let preview = $state<PreviewResponse | null>(null);
let runNonce = $state(0);

function statusClass(status: Job["status"]): string {
  switch (status) {
    case "running":
      return "bg-brand-600 text-white";
    case "done":
      return "bg-emerald-700 text-white";
    case "failed":
      return "bg-red-700 text-white";
    case "cancelled":
      return "bg-amber-600 text-white";
    default:
      return "bg-slate-700 text-slate-100";
  }
}
</script>

<div class="space-y-6">
  <div class="flex flex-wrap items-start justify-between gap-3">
    <div class="space-y-1">
      <h1 class="text-2xl font-semibold text-white">{channel.title}</h1>
      <div class="flex items-center gap-3 text-sm text-slate-400">
        <span>Telegram ID: <span class="text-slate-200">{channel.telegram_id}</span></span>
        {#if channel.username}
          <span>@{channel.username}</span>
        {/if}
        {#if channel.is_active}
          <span class="rounded bg-emerald-900/60 px-2 py-0.5 text-xs text-emerald-200">
            active
          </span>
        {:else}
          <span class="rounded bg-slate-800 px-2 py-0.5 text-xs text-slate-400">inactive</span>
        {/if}
      </div>
    </div>
    <a
      href="/channels"
      class="rounded-md border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-200 hover:bg-slate-700"
    >
      Back to channels
    </a>
  </div>

  <div class="rounded-lg border border-slate-800 bg-slate-900 p-4">
    <ReplaceLinkForm
      channelId={channel.id}
      onPreview={(response) => (preview = response)}
      runNonce={runNonce}
    />
  </div>

  <section class="space-y-2">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <h2 class="text-lg font-semibold text-white">Run history (last 5)</h2>
      <a href="/jobs" class="text-sm text-brand-400 hover:text-brand-300">View all jobs →</a>
    </div>
    {#if recentJobs.length === 0}
      <div
        class="rounded-md border border-slate-800 bg-slate-900 p-4 text-center text-sm text-slate-400"
      >
        No replace-link jobs yet for this channel
      </div>
    {:else}
      <div class="hidden overflow-x-auto rounded-lg border border-slate-800 bg-slate-900 sm:block">
        <table class="min-w-full divide-y divide-slate-800 text-sm">
          <thead class="text-xs text-slate-400">
            <tr>
              <th class="px-3 py-2 text-left font-medium">ID</th>
              <th class="px-3 py-2 text-left font-medium">Status</th>
              <th class="px-3 py-2 text-left font-medium">Progress</th>
              <th class="px-3 py-2 text-left font-medium">Created</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-800">
            {#each recentJobs as job (job.id)}
              <tr class="hover:bg-slate-800/40">
                <td class="px-3 py-2 font-medium text-white">
                  <a href={`/jobs/${job.id}`} class="hover:text-brand-400">#{job.id}</a>
                </td>
                <td class="px-3 py-2">
                  <span
                    class={`rounded-md px-2 py-0.5 text-[10px] font-semibold uppercase ${statusClass(
                      job.status,
                    )}`}
                  >
                    {JOB_STATUS_LABELS[job.status]}
                  </span>
                </td>
                <td class="px-3 py-2 text-slate-300">{job.edited}/{job.total}</td>
                <td class="px-3 py-2 text-slate-300">{job.created_at}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>

      <div class="space-y-3 sm:hidden">
        {#each recentJobs as job (job.id)}
          <div class="rounded-lg border border-slate-800 bg-slate-900 p-3">
            <div class="flex items-start justify-between gap-2">
              <a
                href={`/jobs/${job.id}`}
                class="font-medium text-white hover:text-brand-400"
              >
                #{job.id}
              </a>
              <span
                class={`rounded-md px-2 py-0.5 text-[10px] font-semibold uppercase ${statusClass(
                  job.status,
                )}`}
              >
                {JOB_STATUS_LABELS[job.status]}
              </span>
            </div>
            <div class="mt-2 text-xs text-slate-300">Progress: {job.edited}/{job.total}</div>
            <div class="text-xs text-slate-400">{job.created_at}</div>
          </div>
        {/each}
      </div>
    {/if}
  </section>
</div>

{#if preview}
  <PreviewModal
    previews={preview.previews}
    totalMatches={preview.total_matches}
    compiledPattern={preview.compiled_pattern}
    onEdit={() => (preview = null)}
    onRun={() => {
      preview = null;
      runNonce += 1;
    }}
  />
{/if}