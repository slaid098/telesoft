<script lang="ts">
import PreviewModal from "$lib/components/PreviewModal.svelte";
import ReplaceLinkForm from "$lib/components/ReplaceLinkForm.svelte";
import type { PreviewResponse } from "$lib/types";

type Props = {
  channelId: number;
  onClose?: () => void;
};

const { channelId, onClose }: Props = $props();

let preview = $state<PreviewResponse | null>(null);
let runNonce = $state(0);

function handleKey(event: KeyboardEvent) {
  if (event.key === "Escape" && preview === null) {
    onClose?.();
  }
}

$effect(() => {
  document.addEventListener("keydown", handleKey);
  return () => {
    document.removeEventListener("keydown", handleKey);
  };
});
</script>

<div
  class="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/60 p-4 sm:items-center"
  role="dialog"
  aria-modal="true"
  aria-labelledby="replace-link-modal-title"
>
  <div class="relative my-8 w-full max-w-2xl rounded-lg border border-slate-700 bg-slate-900 p-5 shadow-xl">
    <div class="mb-3 flex items-center justify-between">
      <h2 id="replace-link-modal-title" class="text-lg font-semibold text-white">
        Замена ссылок в канале
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

    <ReplaceLinkForm
      {channelId}
      onPreview={(response) => (preview = response)}
      {runNonce}
    />
  </div>
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