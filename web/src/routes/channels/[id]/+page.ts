import { api } from "$lib/api";
import type { Channel, JobListResponse } from "$lib/types";
import { error, redirect } from "@sveltejs/kit";

import type { PageLoad } from "./$types";

export const prerender = false;
export const ssr = false;

export const load: PageLoad = async ({ params }) => {
  const id = Number(params.id);
  if (!Number.isFinite(id) || id <= 0) {
    error(400, "Некорректный id канала");
  }
  try {
    const [channel, jobsResp] = await Promise.all([
      api.get<Channel>(`/api/channels/${id}`),
      api.get<JobListResponse>("/api/jobs", { channel_id: id, limit: 5 }),
    ]);
    return { channel, recentJobs: jobsResp.jobs };
  } catch (err) {
    const status =
      err instanceof Error && "status" in err ? (err as { status: number }).status : 500;
    if (status === 404) {
      redirect(303, "/channels");
    }
    error(status, "Не удалось загрузить канал");
  }
};
