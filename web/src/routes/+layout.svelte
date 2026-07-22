<script lang="ts">
import "../app.css";
import { goto } from "$app/navigation";
import { page } from "$app/state";
import { api } from "$lib/api";

const { data, children } = $props();

type NavItem = { href: string; label: string; icon: string };

const navItems: NavItem[] = [
  { href: "/channels", label: "Каналы", icon: "📁" },
  { href: "/jobs", label: "Задачи", icon: "⚙️" },
];

const isLogin = $derived(page.url.pathname === "/login");
const username = $derived(data?.user ?? null);

function isActive(item: NavItem): boolean {
  return page.url.pathname.startsWith(item.href);
}

async function handleLogout() {
  try {
    await api.post<{ status: string }>("/api/auth/logout");
  } catch {
    // ignore — redirect to /login regardless
  }
  await goto("/login");
}
</script>

{#if isLogin}
  {@render children()}
{:else}
  <div class="flex h-full min-h-screen flex-col">
    <main class="flex flex-1 flex-col">
      <header
        class="sticky top-0 z-50 flex h-14 shrink-0 items-center justify-between border-b border-slate-800 bg-slate-900 px-4 sm:px-6"
      >
        <div class="flex items-center gap-4">
          <a href="/channels" class="text-lg font-semibold text-white">telesoft</a>
          <nav class="flex items-center gap-2">
            {#each navItems as item (item.href)}
              <a
                href={item.href}
                class="flex items-center gap-2 rounded-md px-3 py-2.5 text-sm font-medium transition-colors
                  {isActive(item)
                  ? "bg-brand-600 text-white"
                  : "text-slate-300 hover:bg-slate-800 hover:text-white"}"
              >
                <span class="text-base" aria-hidden="true">{item.icon}</span>
                <span>{item.label}</span>
              </a>
            {/each}
          </nav>
        </div>
        <div class="flex items-center gap-3">
          {#if username}
            <span class="hidden text-xs text-slate-400 sm:block">
              Вы вошли как <span class="text-slate-200">{username}</span>
            </span>
          {/if}
          <button
            type="button"
            onclick={handleLogout}
            class="rounded-md bg-slate-800 px-3 py-2 text-sm font-medium text-slate-100 hover:bg-slate-700"
          >
            Выйти
          </button>
        </div>
      </header>

      <div class="flex-1 overflow-y-auto p-4 sm:p-6">
        {@render children()}
      </div>
    </main>
  </div>
{/if}