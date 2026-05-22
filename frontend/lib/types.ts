// ── AI Recruiting (legacy) ─────────────────────────────────────────────────

export interface Candidate {
  name: string;
  role_type: string;
  source: string;
  profile_url?: string;
  headline?: string;
  location?: string;
  email?: string;
  skills: string[];
  experience_years?: number;
  notable_work?: string;
  open_source_contributions?: string;
  publications?: string;
  enriched_summary?: string;
  ai_expertise_depth?: string;
  recent_activity?: string;
  community_presence?: string;
  fit_score: number;
  technical_score: number;
  culture_score: number;
  scoring_rationale?: string;
  recommended: boolean;
  outreach_subject?: string;
  outreach_message?: string;
  outreach_channel?: string;
}

export interface PipelineStats {
  sourced: number;
  enriched: number;
  scored: number;
  recommended: number;
  outreached: number;
}

export interface InterviewInsights {
  candidate_name: string;
  key_strengths: string[];
  areas_of_concern: string[];
  technical_assessment?: string;
  cultural_fit_assessment?: string;
  recommendation?: string;
  next_steps: string[];
  summary?: string;
}

// ── Healthcare Shift Staffing ──────────────────────────────────────────────

export interface Shift {
  role: string;
  facility_name: string;
  unit?: string;
  date_str: string;
  start_time: string;
  end_time: string;
  duration_hours: number;
  notes?: string;
  raw_description?: string;
  display_time: string;
  display_label: string;
}

export interface HealthcareProfessional {
  name: string;
  role: string;
  source: string;
  professional_id?: string;
  phone?: string;
  email?: string;
  facility_name?: string;
  unit?: string;
  shifts_at_facility: number;
  shifts_in_unit: number;
  total_shifts: number;
  last_shift_date?: string;
  location?: string;
  // Scored fields
  availability_score: number;
  experience_score: number;
  fit_score: number;
  scoring_rationale?: string;
  recommended: boolean;
  // Outreach
  message_body?: string;
  contact_channel: string;
}

export interface ShiftStats {
  sourced: number;
  scored: number;
  recommended: number;
  contacted: number;
}
