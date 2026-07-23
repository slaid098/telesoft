import { listChannels } from "$lib/api";
import type { ChannelListResponse } from "$lib/types";
import { error } from "@sveltejs/kit";

import type { PageLoad } from "./$types";

export const prerender = false;
export const ssr = false;

export const load: PageLoad = async () => {
  try {
    const data = await listChannels(false);
    return { channels: data.channels, total: data.total };
  } catch (err) {
    const status =
      err instanceof Error && "status" in err ? (err as { status: number }).status : 500;
    error(status, "Не удалось загрузить каналы");
  }
};
