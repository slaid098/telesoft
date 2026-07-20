<script lang="ts">
import { api } from "$lib/api";
import type { Channel, Job, JobListResponse, JobStatus } from "$lib/types";
import { JOB_STATUSES, JOB_STATUS_LABELS } from "$lib/types";

type Props = { data: { jobs: Job[]; total: number; channels: Channel[] } };
const { data }: Props = $props();

const channelsById = $derived(new Map(data.channels.map((c) => [c.id, c])));

let statusFilter = $state<JobStatus | "all">("all");
let localRefresh = $state<Job[] | null>(null);
let error = $state<string | null>(null);
let pollTimer: ReturnType<typeof setInterval> | null = null;

const jobs = $derived.by<Job[]>(() => localRefresh ?? data.jobs);

const filteredJobs = $derived(
  statusFilter === "all" ? jobs : jobs.filter((j) => j.status === statusFilter),
);

const hasRunning = $derived(jobs.some((j) => j.status === "running" || j.status === "pending"));

function channelTitle(id: number): string {
  return channelsById.get(id)?.title ?? `#${id}`;
}

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

async function refresh() {
  try {
    const resp = await api.get<JobListResponse>("/api/jobs", { limit: 50 });
    localRefresh = resp.jobs;
  } catch (err) {
    error = err instanceof Error ? err.message : "Refresh failed";
  }
}

$effect(() => {
  if (!hasRunning) {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
    return;
  }
  if (pollTimer) return;
  pollTimer = setInterval(() => {
    void refresh();
  }, 5000);
  return () => {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  };
});
</script>

<div class="space-y-4">
  <div class="flex flex-wrap items-center justify-between gap-3">
    <h1 class="text-2xl font-semibold text-white">Jobs</h1>
    <div class="flex items-center gap-2">
      <label for="job-status-filter" class="text-xs text-slate-400">Status</label>
      <select
        id="job-status-filter"
        bind:value={statusFilter}
        class="rounded-md border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
      >
        <option value="all">all</option>
        {#each JOB_STATUSES as status (status)}
          <option value={status}>{JOB_STATUS_LABELS[status]}</option>
        {/each}
      </select>
    </div>
  </div>

  {#if error}
    <div class="rounded-md border border-red-900 bg-red-950 px-3 py-2 text-sm text-red-200">
      {error}
    </div>
  {/if}

  {#if hasRunning}
    <p class="text-xs text-slate-400">Auto-refresh every 5 seconds while jobs are running.</p>
  {/if}

  <div class="overflow-x-auto rounded-lg border border-slate-800 bg-slate-900">
    <table class="min-w-full divide-y divide-slate-800 text-sm">
      <thead class="text-xs text-slate-400">
        <tr>
          <th class="px-3 py-2 text-left font-medium">ID</th>
          <th class="px-3 py-2 text-left font-medium">Channel</th>
          <th class="px-3 py-2 text-left font-medium">Pattern</th>
          <th class="px-3 py-2 text-left font-medium">Status</th>
          <th class="px-3 py-2 text-left font-medium">Progress</th>
          <th class="px-3 py-2 text-left font-medium">Created</th>
        </tr>
      </thead>
      <tbody class="divide-y divide-slate-800">
        {#each filteredJobs as job (job.id)}
          <tr class="hover:bg-slate-800/40">
            <td class="px-3 py-2 font-medium text-white">
              <a href={`/jobs/${job.id}`} class="hover:text-brand-400">#{job.id}</a>
            </td>
            <td class="px-3 py-2 text-slate-300">{channelTitle(job.channel_id)}</td>
            <td class="max-w-xs truncate px-3 py-2 text-slate-300" title={job.pattern}>
              {job.pattern}
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
        {:else}
          <tr>
            <td colspan="6" class="px-3 py-8 text-center text-slate-400">No jobs</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
</div>