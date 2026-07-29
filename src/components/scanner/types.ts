export type StageStatus = "pending" | "active" | "done";

export interface ScanStageDef {
  id: string;
  label: string;
  detail: string;
}

export interface ScanStageState extends ScanStageDef {
  status: StageStatus;
  durationMs: number;
}

export interface SocialResult {
  platform: "LinkedIn" | "Facebook" | "Instagram" | "X";
  found: boolean;
  handle?: string;
}

export interface ScanReport {
  id: string;
  url: string;
  domain: string;
  companyName: string;
  contactPerson: string;
  confidence: number;
  scanDurationMs: number;
  scannedAt: string;
  contacts: {
    emails: string[];
    phones: string[];
  };
  gst: {
    number: string;
    verifiedFormat: boolean;
  };
  social: SocialResult[];
  health: {
    ssl: boolean;
    mobileFriendly: boolean;
    loadTimeMs: number;
    seoScore: number;
  };
  stages: { id: string; label: string; durationMs: number }[];
}

export interface RecentScan {
  id: string;
  domain: string;
  confidence: number;
  scannedAt: string;
}
