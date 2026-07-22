<script lang="ts">
import { goto } from "$app/navigation";
import { ApiError, apiErrorMessage, listPatterns, previewReplace, replaceLink } from "$lib/api";
import PatternLibrary from "$lib/components/PatternLibrary.svelte";
import type { PatternListResponse, PreviewResponse, ReplaceMode } from "$lib/types";

type Props = {
  channelId: number;
  onSubmit?: (response: { job_id: number }) => void;
  onPreview?: (response: PreviewResponse) => void;
  runNonce?: number;
};

const { channelId, onSubmit, onPreview, runNonce = 0 }: Props = $props();

const MODES: { value: ReplaceMode; label: string }[] = [
  { value: "simple", label: "Простой" },
  { value: "library", label: "Библиотека паттернов" },
  { value: "advanced", label: "Расширенный" },
];

let mode = $state<ReplaceMode>("simple");
let pattern = $state("");
let newLink = $state("");
let postLink = $state("");
let limit = $state(100);
let fullReplace = $state(true);
let error = $state<string | null>(null);
let submitting = $state(false);
let previewing = $state(false);

let patterns = $state<PatternListResponse | null>(null);
let selectedPatternId = $state<string>("");
let showLibrary = $state(false);
let lastRunNonce = $state(0);

const trimmedPattern = $derived(pattern.trim());
const trimmedNewLink = $derived(newLink.trim());
const trimmedPostLink = $derived(postLink.trim());
const limitValid = $derived(Number.isFinite(limit) && limit >= 1 && limit <= 1000);
const selectedPattern = $derived(
  patterns?.patterns.find((p) => String(p.id) === selectedPatternId) ?? null,
);
const effectivePattern = $derived(
  mode === "library" ? (selectedPattern?.pattern ?? "") : trimmedPattern,
);

const canSubmit = $derived(
  !submitting &&
    !previewing &&
    effectivePattern.length > 0 &&
    trimmedNewLink.length > 0 &&
    trimmedPostLink.length > 0 &&
    limitValid &&
    (mode !== "library" || selectedPattern !== null),
);

async function loadPatterns() {
  try {
    patterns = await listPatterns();
  } catch (err) {
    error = apiErrorMessage(err, "Не удалось загрузить паттерны");
  }
}

$effect(() => {
  if (mode === "library" && patterns === null) {
    void loadPatterns();
  }
});

$effect(() => {
  if (runNonce > 0 && runNonce !== lastRunNonce) {
    lastRunNonce = runNonce;
    void submitJob();
  }
});

function selectMode(next: ReplaceMode) {
  if (next === mode) return;
  mode = next;
  error = null;
}

async function handlePreview() {
  if (!canSubmit) {
    error = "Заполните все обязательные поля";
    return;
  }
  error = null;
  previewing = true;
  try {
    const result = await previewReplace(channelId, {
      pattern: effectivePattern,
      new_link: trimmedNewLink,
      post_link: trimmedPostLink,
      mode,
      full_replace: fullReplace,
      limit,
    });
    onPreview?.(result);
  } catch (err) {
    error = apiErrorMessage(err, "Не удалось выполнить предпросмотр");
  } finally {
    previewing = false;
  }
}

async function submitJob() {
  if (!canSubmit) {
    error = "Заполните все обязательные поля";
    return;
  }
  error = null;
  submitting = true;
  try {
    const result = await replaceLink(channelId, {
      pattern: effectivePattern,
      new_link: trimmedNewLink,
      post_link: trimmedPostLink,
      limit,
      mode,
      full_replace: fullReplace,
    });
    onSubmit?.(result);
    await goto(`/jobs/${result.job_id}`);
  } catch (err) {
    error = apiErrorMessage(err, "Не удалось запустить замену ссылок");
  } finally {
    submitting = false;
  }
}

async function handleSubmit(event: Event) {
  event.preventDefault();
  await submitJob();
}
</script>

<form class="space-y-4" onsubmit={handleSubmit}>
  <h2 class="text-lg font-semibold text-white">Замена ссылки</h2>

  <div role="tablist" class="flex gap-1 rounded-md border border-slate-700 bg-slate-800 p-1">
    {#each MODES as m (m.value)}
      <button
        type="button"
        role="tab"
        aria-selected={mode === m.value}
        aria-controls={`rl-panel-${m.value}`}
        id={`rl-tab-${m.value}`}
        class={`flex-1 rounded px-3 py-1.5 text-sm font-medium transition ${
          mode === m.value
            ? "bg-brand-600 text-white"
            : "text-slate-300 hover:bg-slate-700"
        }`}
        onclick={() => selectMode(m.value)}
      >
        {m.label}
      </button>
    {/each}
  </div>

  {#if mode === "simple"}
    <div
      id="rl-panel-simple"
      role="tabpanel"
      aria-labelledby="rl-tab-simple"
    >
      <label for="rl-pattern" class="mb-1 block text-xs font-medium text-slate-300">
        Найти ссылки
      </label>
      <input
        id="rl-pattern"
        type="text"
        bind:value={pattern}
        placeholder="https://t.me/bot?start=flow-*"
        class="w-full rounded-md border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
        required
      />
      <p class="mt-1 text-xs text-slate-400">Используй <code class="text-brand-300">*</code> для любого текста</p>
    </div>
  {:else if mode === "library"}
    <div
      id="rl-panel-library"
      role="tabpanel"
      aria-labelledby="rl-tab-library"
    >
      <label for="rl-pattern-select" class="mb-1 block text-xs font-medium text-slate-300">
        Паттерн из библиотеки
      </label>
      {#if patterns === null}
        <p class="text-xs text-slate-400">Загрузка…</p>
      {:else if patterns.patterns.length === 0}
        <p class="text-xs text-slate-400">Библиотека пуста. Добавь свой паттерн через «Управление паттернами».</p>
      {:else}
        <select
          id="rl-pattern-select"
          bind:value={selectedPatternId}
          class="w-full rounded-md border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          required
        >
          <option value="" disabled>Выберите паттерн…</option>
          {#each patterns.patterns as p (p.id)}
            <option value={String(p.id)}>
              {p.name}{#if p.description} — {p.description}{/if}
            </option>
          {/each}
        </select>
        {#if selectedPattern}
          <p class="mt-1 text-xs text-slate-400">
            Regex: <code class="text-slate-300">{selectedPattern.pattern}</code>
          </p>
        {/if}
      {/if}
      <button
        type="button"
        class="mt-2 text-xs text-brand-400 hover:text-brand-300"
        onclick={() => (showLibrary = true)}
      >
        Управление паттернами
      </button>
    </div>
  {:else}
    <div
      id="rl-panel-advanced"
      role="tabpanel"
      aria-labelledby="rl-tab-advanced"
    >
      <label for="rl-pattern" class="mb-1 block text-xs font-medium text-slate-300">
        Паттерн (регулярное выражение)
      </label>
      <input
        id="rl-pattern"
        type="text"
        bind:value={pattern}
        placeholder="https://old\\.example\\.com"
        class="w-full rounded-md border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
        required
      />
      <p class="mt-1 text-xs text-slate-400">
        Regex для поиска. Валидация выполняется на бэкенде (ошибка вернётся в ответе).
      </p>
    </div>
  {/if}

  <div>
    <label for="rl-new-link" class="mb-1 block text-xs font-medium text-slate-300">
      Заменить на
    </label>
    <input
      id="rl-new-link"
      type="text"
      bind:value={newLink}
      placeholder="https://new.example.com"
      class="w-full rounded-md border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
      required
    />
  </div>

  <div>
    <label for="rl-post-link" class="mb-1 block text-xs font-medium text-slate-300">
      Ссылка на последний пост
    </label>
    <input
      id="rl-post-link"
      type="text"
      bind:value={postLink}
      placeholder="https://t.me/channel/140"
      class="w-full rounded-md border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
      required
    />
    <p class="mt-1 text-xs text-slate-400">
      Открой последний пост в Telegram → правый клик → Copy Link. Можно вставить ссылку или просто номер поста.
    </p>
  </div>

  <fieldset class="space-y-1.5">
    <legend class="mb-1 text-xs font-medium text-slate-300">Замена</legend>
    <label class="flex items-center gap-2 text-sm text-slate-300">
      <input
        type="radio"
        name="rl-replace-mode"
        checked={fullReplace === true}
        onclick={() => (fullReplace = true)}
        class="border-slate-700 bg-slate-800"
      />
      Полная замена <span class="text-xs text-slate-400">(по умолчанию)</span>
    </label>
    <label class="flex items-center gap-2 text-sm text-slate-300">
      <input
        type="radio"
        name="rl-replace-mode"
        checked={fullReplace === false}
        onclick={() => (fullReplace = false)}
        class="border-slate-700 bg-slate-800"
      />
      Частичная (оставить окончание)
    </label>
    {#if fullReplace === false}
      <p class="text-xs text-slate-400">
        Окончание ссылки после <code class="text-brand-300">*</code> останется в посте.
        Используй <code class="text-brand-300">*</code> чтобы указать где обрезать.
      </p>
    {/if}
  </fieldset>

  <div>
    <label for="rl-limit" class="mb-1 block text-xs font-medium text-slate-300">
      Лимит (последних N постов для сканирования)
    </label>
    <input
      id="rl-limit"
      type="number"
      min="1"
      max="1000"
      step="1"
      bind:value={limit}
      class="w-full rounded-md border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
      required
    />
    <p class="mt-1 text-xs text-slate-400">1-1000, по умолчанию 100</p>
  </div>

  {#if error}
    <div class="rounded-md border border-red-900 bg-red-950 px-3 py-2 text-sm text-red-200">
      {error}
    </div>
  {/if}

  <div class="flex items-center justify-end gap-2">
    <button
      type="button"
      onclick={handlePreview}
      disabled={!canSubmit}
      class="rounded-md border border-slate-600 px-4 py-2.5 text-sm font-semibold text-slate-200 hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
    >
      {previewing ? "Предпросмотр…" : "Предпросмотр"}
    </button>
    <button
      type="submit"
      disabled={!canSubmit}
      class="rounded-md bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-60"
    >
      {submitting ? "Запуск…" : "Запустить"}
    </button>
  </div>
</form>

{#if showLibrary}
  <PatternLibrary
    onClose={() => (showLibrary = false)}
    onPatternsChanged={() => {
      patterns = null;
      void loadPatterns();
    }}
  />
{/if}