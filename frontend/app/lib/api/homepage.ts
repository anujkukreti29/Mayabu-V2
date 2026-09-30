import { apiRequest } from "~/lib/api/client";
import { homepageDiscoverySchema, type HomepageDiscovery } from "~/lib/api/schemas";

export function getHomepageDiscovery(limit = 6, signal?: AbortSignal): Promise<HomepageDiscovery> {
  return apiRequest(`/api/homepage?limit=${limit}`, homepageDiscoverySchema, { signal });
}
