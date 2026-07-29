export interface SearchFilters {
  industry: string;
  country: string;
  provider: string;
  companyType: string;
  minRating: number;
  scoreRange: [number, number];
  cities: string[];
  keywords: string[];
}

export const defaultFilters: SearchFilters = {
  industry: "all",
  country: "all",
  provider: "all",
  companyType: "all",
  minRating: 0,
  scoreRange: [0, 100],
  cities: [],
  keywords: [],
};

export type ProviderRunStatus = "pending" | "searching" | "done";

export interface ProviderRun {
  id: string;
  name: string;
  status: ProviderRunStatus;
  progress: number;
  found: number;
}

export type SearchStage = "idle" | "searching" | "results";
