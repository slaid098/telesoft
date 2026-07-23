<script lang="ts">
import ChannelForm from "$lib/components/ChannelForm.svelte";
import type { Channel } from "$lib/types";

type Props = {
  channel: Channel;
  onSaved?: (channel: Channel) => void;
  onClose?: () => void;
};

const { channel, onSaved, onClose }: Props = $props();

function handleKey(event: KeyboardEvent) {
  if (event.key === "Escape") {
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
  aria-labelledby="edit-channel-modal-title"
>
  <div class="relative my-8 w-full max-w-xl rounded-lg border border-slate-700 bg-slate-900 p-5 shadow-xl">
    <div class="mb-3 flex items-center justify-between">
      <h2 id="edit-channel-modal-title" class="text-lg font-semibold text-white">
        Редактировать канал
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

    <ChannelForm {channel} onSaved={onSaved} onCancel={onClose} />
  </div>
</div>