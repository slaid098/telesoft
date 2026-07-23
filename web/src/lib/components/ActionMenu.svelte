<script lang="ts">
import type { Channel } from "$lib/types";

type Props = {
  channel: Channel;
  onReplace?: () => void;
  onEdit?: () => void;
  onToggleActive?: () => void;
  onDelete?: () => void;
};

const { channel, onReplace, onEdit, onToggleActive, onDelete }: Props = $props();

let open = $state(false);
let container: HTMLDivElement | null = $state(null);

function toggle() {
  open = !open;
}

function close() {
  open = false;
}

function handle(event: MouseEvent) {
  if (container && !container.contains(event.target as Node)) {
    close();
  }
}

function handleKey(event: KeyboardEvent) {
  if (event.key === "Escape" && open) {
    close();
  }
}

function run(cb: (() => void) | undefined) {
  close();
  cb?.();
}

$effect(() => {
  if (open) {
    document.addEventListener("click", handle);
    document.addEventListener("keydown", handleKey);
  }
  return () => {
    document.removeEventListener("click", handle);
    document.removeEventListener("keydown", handleKey);
  };
});
</script>

<div class="relative inline-block" bind:this={container}>
  <button
    type="button"
    aria-label="Действия с каналом"
    aria-haspopup="menu"
    aria-expanded={open}
    onclick={toggle}
    class="inline-flex h-8 w-8 items-center justify-center rounded-md border border-slate-700 bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-white focus:outline-none focus:ring-1 focus:ring-brand-500"
  >
    ⋯
  </button>

  {#if open}
    <ul
      role="menu"
      aria-label="Действия с каналом"
      class="absolute right-0 z-30 mt-1 w-52 overflow-hidden rounded-md border border-slate-700 bg-slate-900 py-1 shadow-xl"
    >
      <li role="menuitem">
        <button
          type="button"
          class="block w-full px-3 py-2 text-left text-sm text-slate-200 hover:bg-slate-800"
          onclick={() => run(onReplace)}
        >
          Заменить ссылки
        </button>
      </li>
      <li role="menuitem">
        <button
          type="button"
          class="block w-full px-3 py-2 text-left text-sm text-slate-200 hover:bg-slate-800"
          onclick={() => run(onEdit)}
        >
          Редактировать
        </button>
      </li>
      <li role="menuitem">
        <button
          type="button"
          class="block w-full px-3 py-2 text-left text-sm text-slate-200 hover:bg-slate-800"
          onclick={() => run(onToggleActive)}
        >
          {#if channel.is_active}
            Деактивировать
          {:else}
            Активировать
          {/if}
        </button>
      </li>
      <li class="border-t border-slate-800" role="separator"></li>
      <li role="menuitem">
        <button
          type="button"
          class="block w-full px-3 py-2 text-left text-sm text-red-300 hover:bg-red-950/60"
          onclick={() => run(onDelete)}
        >
          Удалить
        </button>
      </li>
    </ul>
  {/if}
</div>