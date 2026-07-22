<script lang="ts">
import type { PreviewItem } from "$lib/types";

type Props = {
  previews: PreviewItem[];
  totalMatches: number;
  compiledPattern: string;
  onRun: () => void;
  onEdit: () => void;
};

const { previews, totalMatches, compiledPattern, onRun, onEdit }: Props = $props();
</script>

<div
  class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
  role="dialog"
  aria-modal="true"
  aria-labelledby="preview-title"
>
  <div class="w-full max-w-2xl rounded-lg border border-slate-700 bg-slate-900 p-5 shadow-xl">
    <div class="mb-3 flex items-center justify-between">
      <h2 id="preview-title" class="text-lg font-semibold text-white">Предпросмотр</h2>
      <button
        type="button"
        class="text-slate-400 hover:text-white"
        aria-label="Закрыть"
        onclick={onEdit}
      >
        ×
      </button>
    </div>

    <p class="mb-3 text-sm text-slate-300">
      Найдено: <span class="font-semibold text-white">{totalMatches}</span> совпадений
    </p>

    <div class="space-y-3 max-h-[60vh] overflow-y-auto pr-1">
      {#each previews as item (item.message_id)}
        <div class="rounded-md border border-slate-800 bg-slate-950 p-3">
          <div class="mb-1 text-xs font-medium text-slate-400">Пост #{item.message_id}</div>
          <div class="space-y-1 text-sm">
            <div>
              <span class="text-slate-500">Было:</span>
              <span class="break-all text-slate-200">{item.before}</span>
            </div>
            <div>
              <span class="text-slate-500">Стало:</span>
              <span class="break-all text-emerald-300">{item.after}</span>
            </div>
          </div>
        </div>
      {/each}
    </div>

    <p class="mt-3 text-xs text-slate-500">
      compiled_pattern: <code class="break-all text-slate-400">{compiledPattern}</code>
    </p>

    <div class="mt-4 flex items-center justify-end gap-2">
      <button
        type="button"
        class="rounded-md border border-slate-600 px-4 py-2 text-sm font-semibold text-slate-200 hover:bg-slate-800"
        onclick={onEdit}
      >
        Отменить
      </button>
      <button
        type="button"
        class="rounded-md bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700"
        onclick={onRun}
      >
        Запустить
      </button>
    </div>
  </div>
</div>