<script lang="ts">
import { api } from "$lib/api";
import type { Job, Log, LogListResponse, WsEventPayload } from "$lib/types";
import { JOB_STATUS_LABELS } from "$lib/types";
import { WebSocketClient, type WsMessage } from "$lib/ws";
import { onDestroy, onMount } from "svelte";

type Props = { data: { job: Job; logs: Log[] } };
const { data }: Props = $props();

let job = $state<Job>(data.job);
let logs = $state<Log[]>(data.logs);
let cancelError = $state<string | null>(null);
let cancelling = $state(false);

const progressPct = $derived(
  job.total <= 0 ? 0 : Math.max(0, Math.min(100, Math.trunc((job.edited * 100) / job.total))),
);
const isStoppable = $derived(job.status === "running" || job.status === "pending");

let wsClient: WebSocketClient | null = null;

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

async function refetchLogs() {
  try {
    const resp = await api.get<LogListResponse>(`/api/jobs/${job.id}/logs`);
    logs = resp.logs;
  } catch {
    // ignore — logs already on screen
  }
}

async function refetchJob() {
  try {
    const fresh = await api.get<Job>(`/api/jobs/${job.id}`);
    job = fresh;
  } catch {
    // ignore — stale state acceptable briefly
  }
}

function handleWsMessage(msg: WsMessage) {
  if (msg.type !== "data" && typeof msg.type !== "string") return;
  const payload = (msg.data ?? {}) as WsEventPayload;
  const jobId = Number(payload.job_id ?? -1);
  if (!Number.isFinite(jobId) || jobId !== job.id) return;

  if (msg.type === "progress") {
    job = {
      ...job,
      edited: payload.edited ?? job.edited,
      failed: payload.failed ?? job.failed,
      total: payload.total ?? job.total,
    };
    return;
  }

  if (msg.type === "completed" || msg.type === "failed" || msg.type === "cancelled") {
    const nextStatus = msg.type === "completed" ? "done" : (msg.type as Job["status"]);
    job = {
      ...job,
      status: nextStatus,
      edited: payload.edited ?? job.edited,
      failed: payload.failed ?? job.failed,
      total: payload.total ?? job.total,
      completed_at: new Date().toISOString(),
    };
    void refetchLogs();
  }
}

onMount(() => {
  wsClient = new WebSocketClient();
  wsClient.onMessage(handleWsMessage);
  wsClient.connect();
});

onDestroy(() => {
  wsClient?.close();
  wsClient = null;
});

async function handleCancel() {
  if (!isStoppable) return;
  cancelling = true;
  cancelError = null;
  try {
    await api.post<{ job_id: number; status: string }>(`/api/jobs/${job.id}/cancel`);
    await refetchJob();
  } catch (err) {
    cancelError = err instanceof Error ? err.message : "Cancel failed";
  } finally {
    cancelling = false;
  }
}
</script>

<div class="space-y-6">
  <div class="flex flex-wrap items-start justify-between gap-3">
    <div class="space-y-1">
      <div class="flex items-center gap-2">
        <h1 class="text-2xl font-semibold text-white">Job #{job.id}</h1>
        <span
          class={`rounded-md px-2 py-0.5 text-[10px] font-semibold uppercase ${statusClass(
            job.status,
          )}`}
        >
          {JOB_STATUS_LABELS[job.status]}
        </span>
      </div>
      <div class="text-sm text-slate-400 flex flex-col space-y-1 sm:flex-row sm:space-y-0 sm:gap-3">
        <span>
          Channel: <span class="text-slate-200">#{job.channel_id}</span>
        </span>
        <span>
          Pattern: <span class="text-slate-200">{job.pattern}</span>
        </span>
      </div>
      <div class="text-sm text-slate-400">
        New link: <span class="text-slate-200">{job.new_link}</span>
      </div>
    </div>
    <a
      href="/jobs"
      class="rounded-md border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-200 hover:bg-slate-700"
    >
      Back to jobs
    </a>
  </div>

  <div class="rounded-lg border border-slate-800 bg-slate-900 p-4">
    <div class="flex items-center justify-between text-xs text-slate-400">
      <span>Progress: {job.edited}/{job.total || "?"}</span>
      <span>{progressPct}%</span>
    </div>
    <div class="mt-2 h-2 w-full overflow-hidden rounded-full bg-slate-800">
      <div
        class="h-full rounded-full bg-brand-500 transition-all"
        style={`width: ${progressPct}%`}
      >
      </div>
    </div>
    <div class="mt-2 text-xs text-slate-400">
      Edited: <span class="text-emerald-300">{job.edited}</span> · Failed:
      <span class="text-red-300">{job.failed}</span>
    </div>

    {#if job.status === "done" && job.total === 0}
      <div
        class="mt-3 rounded-md border border-amber-900 bg-amber-950 px-3 py-2 text-sm text-amber-200"
      >
        No posts matched the pattern. Check if the channel has posts or if your pattern is correct.
      </div>
    {/if}

    {#if isStoppable}
      <div class="mt-3 flex items-center gap-2">
        <button
          type="button"
          onclick={handleCancel}
          disabled={cancelling}
          class="rounded-md bg-red-700 px-3 py-2.5 text-sm font-medium text-white hover:bg-red-800 disabled:opacity-60"
        >
          {cancelling ? "Cancelling…" : "Cancel job"}
        </button>
      </div>
    {/if}

    {#if cancelError}
      <div
        class="mt-2 rounded-md border border-red-900 bg-red-950 px-3 py-2 text-sm text-red-200"
      >
        {cancelError}
      </div>
    {/if}
  </div>

  <section class="space-y-2">
    <h2 class="text-lg font-semibold text-white">Logs ({logs.length})</h2>
    {#if logs.length === 0}
      <div
        class="rounded-md border border-slate-800 bg-slate-900 p-4 text-center text-sm text-slate-400"
      >
        No logs yet — logs appear as the job progresses
      </div>
    {:else}
      <div class="overflow-x-auto rounded-lg border border-slate-800 bg-slate-900 sm:block">
        <table class="min-w-full divide-y divide-slate-800 text-sm">
          <thead class="text-xs text-slate-400">
            <tr>
              <th class="px-3 py-2 text-left font-medium">Message ID</th>
              <th class="px-3 py-2 text-left font-medium">Success</th>
              <th class="px-3 py-2 text-left font-medium">Error</th>
              <th class="px-3 py-2 text-left font-medium">Old text</th>
              <th class="px-3 py-2 text-left font-medium">Edited at</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-800">
            {#each logs as log (log.id)}
              <tr class="hover:bg-slate-800/40">
                <td class="px-3 py-2 text-slate-300">{log.message_id}</td>
                <td class="px-3 py-2">
                  {#if log.success}
                    <span class="text-emerald-400">✓</span>
                  {:else}
                    <span class="text-red-400">✗</span>
                  {/if}
                </td>
                <td class="max-w-xs truncate px-3 py-2 text-slate-300" title={log.error ?? ""}>
                  {log.error ?? "—"}
                </td>
                <td class="max-w-xs truncate px-3 py-2 text-slate-300" title={log.old_text ?? ""}>
                  {log.old_text ?? "—"}
                </td>
                <td class="px-3 py-2 text-slate-300">{log.edited_at}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>

      <div class="space-y-3 sm:hidden">
        {#each logs as log (log.id)}
          <div class="rounded-lg border border-slate-800 bg-slate-900 p-3">
            <div class="flex items-center justify-between gap-2">
              <span class="text-sm text-slate-300">#{log.message_id}</span>
              {#if log.success}
                <span class="text-emerald-400">✓</span>
              {:else}
                <span class="text-red-400">✗</span>
              {/if}
            </div>
            <dl class="mt-2 space-y-1 text-xs text-slate-300">
              <div class="flex justify-between gap-2">
                <dt class="text-slate-400">Error</dt>
                <dd class="truncate" title={log.error ?? ""}>{log.error ?? "—"}</dd>
              </div>
              <div class="flex justify-between gap-2">
                <dt class="text-slate-400">Old text</dt>
                <dd class="truncate" title={log.old_text ?? ""}>{log.old_text ?? "—"}</dd>
              </div>
              <div class="flex justify-between gap-2">
                <dt class="text-slate-400">Edited at</dt>
                <dd>{log.edited_at}</dd>
              </div>
            </dl>
          </div>
        {/each}
      </div>
    {/if}
  </section>
</div>