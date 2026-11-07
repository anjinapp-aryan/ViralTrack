/**
 * The results grid: as many columns of at least 15rem as the content width allows (one column on phones,
 * two on tablets, four at 1440 px and five at 1664 px with the sidebar open), so cards never stretch wide.
 */
export const RESULTS_GRID =
  'grid gap-x-5 gap-y-6 [grid-template-columns:repeat(auto-fill,minmax(min(100%,15rem),1fr))]'
