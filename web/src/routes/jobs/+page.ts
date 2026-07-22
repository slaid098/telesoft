import { api } from "$lib/api";
import type { ChannelListResponse, JobListResponse } from "$lib/types";
import { error } from "@sveltejs/kit";

import type { PageLoad } from "./$types";

export const prerender = false;
export const ssr = false;

export const load: PageLoad = async () => {
  try {
    const [jobsResp, channelsResp] = await Promise.all([
      api.get<JobListResponse>("/api/jobs", { limit: 50 }),
      api.get<ChannelListResponse>("/api/channels"),
    ]);
    return { jobs: jobsResp.jobs, total: jobsResp.total, channels: channelsResp.channels };
  } catch (err) {
    const status =
      err instanceof Error && "status" in err ? (err as { status: number }).status : 500;
    error(status, "Не удалось загрузить задачи");
  }
};
