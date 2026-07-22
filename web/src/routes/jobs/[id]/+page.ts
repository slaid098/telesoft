import { api } from "$lib/api";
import type { Job, LogListResponse } from "$lib/types";
import { error, redirect } from "@sveltejs/kit";

import type { PageLoad } from "./$types";

export const prerender = false;
export const ssr = false;

export const load: PageLoad = async ({ params }) => {
  const id = Number(params.id);
  if (!Number.isFinite(id) || id <= 0) {
    error(400, "Некорректный id задачи");
  }
  try {
    const [job, logsResp] = await Promise.all([
      api.get<Job>(`/api/jobs/${id}`),
      api.get<LogListResponse>(`/api/jobs/${id}/logs`),
    ]);
    return { job, logs: logsResp.logs };
  } catch (err) {
    const status =
      err instanceof Error && "status" in err ? (err as { status: number }).status : 500;
    if (status === 404) {
      redirect(303, "/jobs");
    }
    error(status, "Не удалось загрузить задачу");
  }
};
