<script lang="ts">
import { goto } from "$app/navigation";
import { page } from "$app/state";
import { ApiError, api } from "$lib/api";

let username = $state("");
let password = $state("");
let error = $state<string | null>(null);
let loading = $state(false);

const redirectTo = new URLSearchParams(page.url.search).get("redirectTo") ?? "/channels";
const canSubmit = $derived(username.trim().length > 0 && password.length > 0 && !loading);

async function handleSubmit(event: Event) {
  event.preventDefault();
  error = null;
  if (!username.trim() || !password) {
    error = "Введите имя пользователя и пароль";
    return;
  }
  loading = true;
  try {
    await api.post<{ status: string }>("/api/auth/login", {
      username: username.trim(),
      password,
    });
    await goto(redirectTo, { replaceState: true });
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) {
      error = "Неверные учётные данные";
    } else if (err instanceof ApiError) {
      error = err.message || "Не удалось войти";
    } else {
      error = "Ошибка сети";
    }
  } finally {
    loading = false;
  }
}
</script>

<div class="flex min-h-screen items-center justify-center bg-slate-950 px-4">
  <div class="w-full max-w-sm rounded-lg border border-slate-800 bg-slate-900 p-6 shadow-xl">
    <h1 class="mb-1 text-2xl font-semibold text-white">telesoft</h1>
    <p class="mb-6 text-sm text-slate-400">Войдите, чтобы продолжить</p>

    <form class="space-y-4" onsubmit={handleSubmit}>
      <div>
        <label for="username" class="mb-1 block text-xs font-medium text-slate-300">
          Имя пользователя
        </label>
        <input
          id="username"
          name="username"
          type="text"
          autocomplete="username"
          bind:value={username}
          class="w-full rounded-md border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          placeholder="admin"
          required
        />
      </div>

      <div>
        <label for="password" class="mb-1 block text-xs font-medium text-slate-300">
          Пароль
        </label>
        <input
          id="password"
          name="password"
          type="password"
          autocomplete="current-password"
          bind:value={password}
          class="w-full rounded-md border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          placeholder="••••••••"
          required
        />
      </div>

      {#if error}
        <div class="rounded-md border border-red-900 bg-red-950 px-3 py-2 text-sm text-red-200">
          {error}
        </div>
      {/if}

      <button
        type="submit"
        disabled={!canSubmit}
        class="w-full rounded-md bg-brand-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {loading ? "Вход…" : "Войти"}
      </button>
    </form>
  </div>
</div>