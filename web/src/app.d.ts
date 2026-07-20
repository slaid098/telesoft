import type { Page } from "@sveltejs/kit";
import type { Writable } from "svelte/store";

declare global {
  namespace App {
    interface Error {
      message: string;
      code?: string;
    }
    interface Locals {
      user: string | null;
    }
    interface PageData {
      user?: string | null;
    }
    interface PageState {}
    interface Platform {}
    type PageStore = Writable<Page>;
  }
}
