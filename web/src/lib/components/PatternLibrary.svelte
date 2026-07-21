<script lang="ts">
import { apiErrorMessage, createPattern, deletePattern, listPatterns } from "$lib/api";
import type { PatternListResponse, PatternResponse } from "$lib/types";

type Props = {
  onClose: () => void;
  onPatternsChanged?: () => void;
};

const { onClose, onPatternsChanged }: Props = $props();

let patterns = $state<PatternResponse[]>([]);
let loading = $state(true);
let error = $state<string | null>(null);

let newName = $state("");
let newPattern = $state("");
let newDescription = $state("");
let creating = $state(false);

async function load() {
  loading = true;
  error = null;
  try {
    const resp: PatternListResponse = await listPatterns();
    patterns = resp.patterns;
  } catch (err) {
    error = apiErrorMessage(err, "Failed to load patterns");
  } finally {
    loading = false;
  }
}

async function handleCreate(event: Event) {
  event.preventDefault();
  if (newName.trim().length === 0 || newPattern.trim().length === 0) {
    error = "Name и pattern обязательны";
    return;
  }
  creating = true;
  error = null;
  try {
    await createPattern({
      name: newName.trim(),
      pattern: newPattern.trim(),
      description: newDescription.trim() || undefined,
    });
    newName = "";
    newPattern = "";
    newDescription = "";
    await load();
    onPatternsChanged?.();
  } catch (err) {
    error = apiErrorMessage(err, "Failed to create pattern");
  } finally {
    creating = false;
  }
}

async function handleDelete(id: number) {
  if (!window.confirm("Удалить паттерн?")) return;
  error = null;
  try {
    await deletePattern(id);
    await load();
    onPatternsChanged?.();
  } catch (err) {
    error = apiErrorMessage(err, "Failed to delete pattern");
  }
}

void load();
</script>

<div
  class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
  role="dialog"
  aria-modal="true"
  aria-labelledby="pattern-library-title"
>
  <div class="w-full max-w-2xl rounded-lg border border-slate-700 bg-slate-900 p-5 shadow-xl">
    <div class="mb-3 flex items-center justify-between">
      <h2 id="pattern-library-title" class="text-lg font-semibold text-white">
        Управление паттернами
      </h2>
      <button
        type="button"
        class="text-slate-400 hover:text-white"
        aria-label="Закрыть"
        onclick={onClose}
      >
        ×
      </button>
    </div>

    {#if error}
      <div class="mb-3 rounded-md border border-red-900 bg-red-950 px-3 py-2 text-sm text-red-200">
        {error}
      </div>
    {/if}

    <div class="max-h-60 space-y-2 overflow-y-auto pr-1">
      {#if loading}
        <p class="text-sm text-slate-400">Загрузка…</p>
      {:else if patterns.length === 0}
        <p class="text-sm text-slate-400">Паттернов пока нет.</p>
      {:else}
        {#each patterns as p (p.id)}
          <div class="rounded-md border border-slate-800 bg-slate-950 p-3">
            <div class="flex items-start justify-between gap-2">
              <div class="min-w-0">
                <div class="flex items-center gap-2">
                  <span class="font-medium text-white">{p.name}</span>
                  {#if p.is_builtin}
                    <span
                      class="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] uppercase text-slate-400"
                      title="встроенный"
                    >
                      built-in
                    </span>
                  {/if}
                </div>
                {#if p.description}
                  <p class="mt-0.5 text-xs text-slate-400">{p.description}</p>
                {/if}
                <code class="mt-1 block break-all text-xs text-slate-300">{p.pattern}</code>
              </div>
              {#if !p.is_builtin}
                <button
                  type="button"
                  class="shrink-0 rounded border border-red-900 px-2 py-1 text-xs text-red-300 hover:bg-red-950"
                  onclick={() => handleDelete(p.id)}
                >
                  Удалить
                </button>
              {/if}
            </div>
          </div>
        {/each}
      {/if}
    </div>

    <form class="mt-4 space-y-2" onsubmit={handleCreate}>
      <h3 class="text-sm font-medium text-slate-200">Добавить свой паттерн</h3>
      <input
        type="text"
        bind:value={newName}
        placeholder="Название"
        class="w-full rounded-md border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
      />
      <input
        type="text"
        bind:value={newPattern}
        placeholder="Regex (напр. https://t\\.me/bot\\?start=flow-.* )"
        class="w-full rounded-md border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
      />
      <input
        type="text"
        bind:value={newDescription}
        placeholder="Описание (необязательно)"
        class="w-full rounded-md border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
      />
      <div class="flex justify-end">
        <button
          type="submit"
          disabled={creating}
          class="rounded-md bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {creating ? "Добавление…" : "Добавить"}
        </button>
      </div>
    </form>
  </div>
</div>