import { redirect } from "react-router";
import type { LoaderFunctionArgs } from "react-router";

/** Legacy path — keep /login working as an alias of /sign-in. */
export function loader({ request }: LoaderFunctionArgs) {
  const url = new URL(request.url);
  const next = url.searchParams.toString();
  throw redirect(next ? `/sign-in?${next}` : "/sign-in");
}

export default function LoginAlias() {
  return null;
}
