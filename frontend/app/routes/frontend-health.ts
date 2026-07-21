export function loader() {
  return Response.json(
    { service: "mayabu-frontend", status: "ok", rendering: "react-router-ssr" },
    { headers: { "Cache-Control": "no-store" } },
  );
}
