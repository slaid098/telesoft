import { browser } from "$app/environment";
import { api } from "$lib/api";
import type { MeResponse } from "$lib/types";
import { redirect } from "@sveltejs/kit";

import type { LayoutLoad } from "./$types";

export const prerender = false;
export const ssr = false;

const PUBLIC_PATHS = new Set(["/login"]);

export const load: LayoutLoad = async ({ url }) => {
  const { pathname } = url;

  if (PUBLIC_PATHS.has(pathname)) {
    return {};
  }

  if (!browser) {
    return { user: null };
  }

  try {
    const data = await api.get<MeResponse>("/api/auth/me");
    return { user: data.user };
  } catch {
    const target = `${pathname}${url.search}`;
    const params = new URLSearchParams({ redirectTo: target });
    redirect(303, `/login?${params.toString()}`);
  }
};
