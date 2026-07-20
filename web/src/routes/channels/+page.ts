import { api } from "$lib/api";
import type { ChannelListResponse } from "$lib/types";
import { error } from "@sveltejs/kit";

import type { PageLoad } from "./$types";

export const prerender = false;
export const ssr = false;

export const load: PageLoad = async () => {
  try {
    const data = await api.get<ChannelListResponse>("/api/channels");
    return { channels: data.channels, total: data.total };
  } catch (err) {
    const status =
      err instanceof Error && "status" in err ? (err as { status: number }).status : 500;
    error(status, "Failed to load channels");
  }
};
