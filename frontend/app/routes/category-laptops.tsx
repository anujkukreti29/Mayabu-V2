import { createCategoryLanding } from "~/lib/category/create-landing-route";

const landing = createCategoryLanding("laptop");
export const meta = landing.meta;
export const loader = landing.loader;
export default landing.Component;
export const HydrateFallback = landing.HydrateFallback;
