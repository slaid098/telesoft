<script lang="ts">
import { api } from "$lib/api";
import type { Channel, Job, JobListResponse, JobStatus } from "$lib/types";
import { JOB_STATUSES, JOB_STATUS_LABELS } from "$lib/types";

type Props = { data: { jobs: Job[]; total: number; channels: Channel[] } };
const { data }: Props = $props();

const pageSize = 20;

const channelsById = $derived(new Map(data.channels.map((c) => [c.id, c])));

let page = $state(1);
let statusFilter = $state<JobStatus | "all">("all");
let localRefresh = $state<Job[] | null>(null);
let localTotal = $state<number | null>(null);
let error = $state<string | null>(null);
let pollTimer: ReturnType<typeof setInterval> | null = null;

const total = $derived.by<number>(() => localTotal ?? data.total);
const jobs = $derived.by<Job[]>(() => localRefresh ?? data.jobs);

const totalPages = $derived(total <= 0 ? 1 : Math.ceil(total / pageSize));

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
    const offset = (page - 1) * pageSize;
    const query: Record<string, string | number | boolean | undefined | null> = {
      limit: pageSize,
      offset,
    };
    if (statusFilter !== "all") query.status = statusFilter;
    const resp = await api.get<JobListResponse>("/api/jobs", query);
    localRefresh = resp.jobs;
    localTotal = resp.total;
  } catch (err) {
    error = err instanceof Error ? err.message : "Не удалось обновить";
  }
}

async function goToPage(next: number) {
  if (next < 1 || next > totalPages || next === page) return;
  page = next;
  await refresh();
}

async function onStatusFilterChange() {
  page = 1;
  await refresh();
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
    <h1 class="text-2xl font-semibold text-white">Задачи</h1>
    <div class="flex items-center gap-2">
      <label for="job-status-filter" class="text-xs text-slate-400">Статус</label>
      <select
        id="job-status-filter"
        bind:value={statusFilter}
        onchange={onStatusFilterChange}
        class="rounded-md border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
      >
        <option value="all">все</option>
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
    <p class="text-xs text-slate-400">Авто-обновление каждые 5 секунд, пока задачи выполняются.</p>
  {/if}

  <div class="hidden overflow-x-auto rounded-lg border border-slate-800 bg-slate-900 sm:block">
    <table class="min-w-full divide-y divide-slate-800 text-sm">
      <thead class="text-xs text-slate-400">
        <tr>
          <th class="px-3 py-2 text-left font-medium">ID</th>
          <th class="px-3 py-2 text-left font-medium">Канал</th>
          <th class="px-3 py-2 text-left font-medium">Паттерн</th>
          <th class="px-3 py-2 text-left font-medium">Статус</th>
          <th class="px-3 py-2 text-left font-medium">Прогресс</th>
          <th class="px-3 py-2 text-left font-medium">Создан</th>
        </tr>
      </thead>
      <tbody class="divide-y divide-slate-800">
        {#each jobs as job (job.id)}
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
            <td colspan="6" class="px-3 py-8 text-center text-slate-400">Нет задач</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>

  <div class="space-y-3 sm:hidden">
    {#each jobs as job (job.id)}
      <div class="rounded-lg border border-slate-800 bg-slate-900 p-3">
        <div class="flex items-center justify-between gap-2">
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
        <dl class="mt-2 space-y-1 text-xs text-slate-300">
          <div class="flex justify-between gap-2">
            <dt class="text-slate-400">Канал</dt>
            <dd>{channelTitle(job.channel_id)}</dd>
          </div>
          <div class="flex justify-between gap-2">
            <dt class="text-slate-400">Паттерн</dt>
            <dd class="truncate" title={job.pattern}>{job.pattern}</dd>
          </div>
          <div class="flex justify-between gap-2">
            <dt class="text-slate-400">Прогресс</dt>
            <dd>{job.edited}/{job.total}</dd>
          </div>
          <div class="flex justify-between gap-2">
            <dt class="text-slate-400">Создан</dt>
            <dd>{job.created_at}</dd>
          </div>
        </dl>
      </div>
    {:else}
      <div class="rounded-lg border border-slate-800 bg-slate-900 p-4 text-center text-sm text-slate-400">
        Нет задач
      </div>
    {/each}
  </div>

  {#if totalPages > 1}
    <nav
      aria-label="Пагинация задач"
      class="flex items-center justify-center gap-1 pt-2"
    >
      <button
        type="button"
        onclick={() => goToPage(page - 1)}
        disabled={page <= 1}
        class="rounded-md border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-200 hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
      >
        ‹ Пред.
      </button>

      {#each Array.from({ length: totalPages }, (_, i) => i + 1) as p (p)}
        <button
          type="button"
          onclick={() => goToPage(p)}
          aria-current={p === page ? "page" : undefined}
          class={`rounded-md px-3 py-2 text-sm ${
            p === page
              ? "border border-brand-500 bg-brand-600 font-semibold text-white"
              : "border border-slate-700 bg-slate-800 text-slate-200 hover:bg-slate-700"
          }`}
        >
          {p}
        </button>
      {/each}

      <button
        type="button"
        onclick={() => goToPage(page + 1)}
        disabled={page >= totalPages}
        class="rounded-md border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-200 hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
      >
        След. ›
      </button>
    </nav>
  {/if}
</div>