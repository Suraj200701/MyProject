export type LeadStatus = "new" | "contacted" | "qualified" | "converted" | "lost";

export interface Lead {
  id: string;
  company: string;
  industry: string;
  city: string;
  country: string;
  contactName: string;
  email: string;
  phone: string;
  website: string;
  rating: number;
  revenue: string;
  leadScore: number;
  status: LeadStatus;
  companyType: string;
  provider: string;
  tags: string[];
  createdAt: string;
  gst?: string;
  lat: number;
  lng: number;
  aiSummary: string;
}

export interface ApiProvider {
  id: string;
  name: string;
  category: "Search" | "Maps" | "Business" | "CRM" | "AI";
  status: "healthy" | "degraded" | "down";
  usage: number;
  limit: number;
  latencyMs: number;
  logo: string;
  description: string;
  connected: boolean;
}

export interface SearchHistoryItem {
  id: string;
  query: string;
  location: string;
  results: number;
  createdAt: string;
  /** "skipped" = a provider never ran (no credentials); not a failure. */
  status: "completed" | "running" | "failed" | "skipped";
}

export interface NotificationItem {
  id: string;
  title: string;
  description: string;
  type: "search" | "export" | "api" | "recommendation" | "system";
  read: boolean;
  createdAt: string;
}
