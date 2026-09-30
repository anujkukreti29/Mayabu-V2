import { redirect } from "react-router";

/** Legacy smartphone path — keep bookmarks working. */
export function loader() {
  return redirect("/smartphones", 301);
}
