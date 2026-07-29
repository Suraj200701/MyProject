import type { LucideIcon } from "lucide-react";
import {
  Factory,
  Truck,
  PanelsTopLeft,
  Network,
  HardHat,
  Users2,
  MoreHorizontal,
} from "lucide-react";

export interface OnboardingAnswers {
  businessType: string | null;
  industries: string[];
  dataSources: string[];
  countries: string[];
  volume: string | null;
  teamSize: string | null;
}

export const initialAnswers: OnboardingAnswers = {
  businessType: null,
  industries: [],
  dataSources: [],
  countries: [],
  volume: null,
  teamSize: null,
};

export interface BusinessTypeOption {
  value: string;
  label: string;
  description: string;
  icon: LucideIcon;
}

export const BUSINESS_TYPES: BusinessTypeOption[] = [
  { value: "manufacturer", label: "Manufacturer", description: "You produce goods or equipment", icon: Factory },
  { value: "distributor-dealer", label: "Distributor/Dealer", description: "You resell or distribute products", icon: Truck },
  { value: "panel-builder", label: "Panel Builder", description: "You assemble electrical panels", icon: PanelsTopLeft },
  { value: "system-integrator", label: "System Integrator", description: "You integrate systems for clients", icon: Network },
  { value: "epc-contractor", label: "EPC Contractor", description: "Engineering, procurement & construction", icon: HardHat },
  { value: "agency-consultant", label: "Agency/Consultant", description: "You advise or serve other businesses", icon: Users2 },
  { value: "other", label: "Other", description: "Something else entirely", icon: MoreHorizontal },
];

export const INDUSTRIES: string[] = [
  "Electrical Dealers",
  "Panel Builders",
  "Manufacturers",
  "OEM",
  "System Integrators",
  "EPC Companies",
  "Industrial Automation",
  "Other",
];

export interface DataSourceOption {
  value: string;
  label: string;
  emoji: string;
}

// Hardcoded locally per onboarding scope — intentionally not sourced from mock-data.ts.
export const DATA_SOURCES: DataSourceOption[] = [
  { value: "google-places", label: "Google Places", emoji: "📍" },
  { value: "mappls", label: "Mappls", emoji: "🗺️" },
  { value: "indiamart", label: "IndiaMART", emoji: "🛒" },
  { value: "tradeindia", label: "TradeIndia", emoji: "🤝" },
  { value: "justdial", label: "JustDial", emoji: "📞" },
  { value: "linkedin", label: "LinkedIn", emoji: "💼" },
  { value: "not-sure", label: "I'm not sure yet", emoji: "🤔" },
];

export interface CountryOption {
  value: string;
  label: string;
  flag: string;
}

export const COUNTRIES: CountryOption[] = [
  { value: "india", label: "India", flag: "🇮🇳" },
  { value: "uae", label: "UAE", flag: "🇦🇪" },
  { value: "singapore", label: "Singapore", flag: "🇸🇬" },
  { value: "united-states", label: "United States", flag: "🇺🇸" },
  { value: "united-kingdom", label: "United Kingdom", flag: "🇬🇧" },
  { value: "indonesia", label: "Indonesia", flag: "🇮🇩" },
  { value: "other", label: "Other", flag: "🌍" },
];

export interface VolumeOption {
  value: string;
  label: string;
  description: string;
}

export const VOLUME_OPTIONS: VolumeOption[] = [
  { value: "lt-500", label: "< 500", description: "leads per month" },
  { value: "500-2000", label: "500 – 2,000", description: "leads per month" },
  { value: "2000-10000", label: "2,000 – 10,000", description: "leads per month" },
  { value: "gt-10000", label: "10,000+", description: "leads per month" },
];

export interface TeamSizeOption {
  value: string;
  label: string;
  description: string;
}

export const TEAM_SIZE_OPTIONS: TeamSizeOption[] = [
  { value: "just-me", label: "Just me", description: "Solo operator" },
  { value: "2-10", label: "2 – 10", description: "Small team" },
  { value: "11-50", label: "11 – 50", description: "Growing team" },
  { value: "51-200", label: "51 – 200", description: "Mid-size org" },
  { value: "200-plus", label: "200+", description: "Enterprise org" },
];

export const CHECKLIST_ITEMS: string[] = [
  "Configuring lead search…",
  "Connecting data providers…",
  "Personalizing your dashboard…",
  "Finalizing your workspace…",
];
