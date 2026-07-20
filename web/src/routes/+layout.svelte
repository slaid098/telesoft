<script lang="ts">
import "../app.css";
import { goto } from "$app/navigation";
import { page } from "$app/state";
import { api } from "$lib/api";

const { data, children } = $props();

type NavItem = { href: string; label: string; icon: string };

const navItems: NavItem[] = [
  { href: "/channels", label: "Channels", icon: "📁" },
  { href: "/jobs", label: "Jobs", icon: "⚙️" },
];

const isLogin = $derived(page.url.pathname === "/login");
const username = $derived(data?.user ?? null);

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
  <div class="flex h-full min-h-screen flex-col sm:flex-row">
    <aside
      class="hidden w-60 shrink-0 border-r border-slate-800 bg-slate-900 sm:flex sm:flex-col"
    >
      <div class="flex h-14 items-center px-4 text-lg font-semibold text-white">telesoft</div>
      <nav class="flex-1 space-y-1 px-2 py-2">
        {#each navItems as item (item.href)}
          <a
            href={item.href}
            class="flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors
              {page.url.pathname.startsWith(item.href)
              ? "bg-brand-600 text-white"
              : "text-slate-300 hover:bg-slate-800 hover:text-white"}"
          >
            <span class="text-base" aria-hidden="true">{item.icon}</span>
            <span>{item.label}</span>
          </a>
        {/each}
      </nav>
      <div class="border-t border-slate-800 p-3">
        {#if username}
          <div class="mb-2 truncate px-2 text-xs text-slate-400">
            Signed in as <span class="text-slate-200">{username}</span>
          </div>
        {/if}
        <button
          type="button"
          onclick={handleLogout}
          class="w-full rounded-md bg-slate-800 px-3 py-2 text-sm font-medium text-slate-100 hover:bg-slate-700"
        >
          Logout
        </button>
      </div>
    </aside>

    <main class="flex flex-1 flex-col">
      <header
        class="flex h-14 shrink-0 items-center justify-between border-b border-slate-800 bg-slate-900 px-4 sm:px-6"
      >
        <span class="text-base font-semibold text-white sm:hidden">telesoft</span>
        {#if username}
          <span class="hidden text-xs text-slate-400 sm:block">
            Signed in as <span class="text-slate-200">{username}</span>
          </span>
        {/if}
      </header>

      <div class="flex-1 overflow-y-auto p-4 sm:p-6">
        {@render children()}
      </div>

      <nav
        class="grid grid-cols-1 border-t border-slate-800 bg-slate-900 sm:hidden"
        aria-label="Mobile navigation"
      >
        {#each navItems as item (item.href)}
          <a
            href={item.href}
            class="flex flex-col items-center gap-1 py-2 text-[10px] font-medium transition-colors
              {page.url.pathname.startsWith(item.href)
              ? "text-brand-500"
              : "text-slate-400 hover:text-slate-200"}"
          >
            <span class="text-lg" aria-hidden="true">{item.icon}</span>
            <span>{item.label}</span>
          </a>
        {/each}
      </nav>
    </main>
  </div>
{/if}