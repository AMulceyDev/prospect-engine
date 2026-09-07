export type WebStatus = 'site' | 'none' | 'unknown'
export type OpportunityKey = 'forte' | 'moyenne' | 'faible'
export type SignalStyle = 'mix' | 'badge' | 'score' | 'grade'

// Mirror api/app/schemas/company.py exactly

export interface DomainEntry {
  domain: string
  source: 'rne' | 'osm'
}

export interface WebsiteRead {
  url: string
  domain: string
  source: string
  dns_resolved: boolean
  http_status: number | null
  final_url: string | null
  is_https: boolean | null
  confidence: number
  is_selected: boolean
}

export interface LighthouseScores {
  performance: number | null
  accessibility: number | null
  best_practices: number | null
  seo: number | null
}

export interface LighthouseSeoPoint {
  title: string
  pass: boolean | null
  display_value: string | null
}

export interface LighthouseMetric {
  display_value: string | null
  score: number | null
}

export interface LighthouseSeo {
  meta_description?: LighthouseSeoPoint
  document_title?: LighthouseSeoPoint
  canonical?: LighthouseSeoPoint
  robots_txt?: LighthouseSeoPoint
  is_crawlable?: LighthouseSeoPoint
  structured_data?: LighthouseSeoPoint
  image_alt?: LighthouseSeoPoint
  http_status_code?: LighthouseSeoPoint
  font_size?: LighthouseSeoPoint
  hreflang?: LighthouseSeoPoint
  metrics?: Record<string, LighthouseMetric>
}

export interface LighthouseRemark {
  id: string
  category: string
  title: string
  display_value: string | null
  score: number | null
}

export interface AnalysisRead {
  ownership_confirmed: boolean
  ownership_signals: Record<string, unknown>
  internal_links: string[]
  external_links: string[]
  has_legal_page: boolean
  has_contact_info: boolean
  provider_hint: string | null
  tech_stack: string[]
  obsolete_tech: string[]
  wayback_first_seen: string | null
  sitemap_last_modified: string | null
  sitemap_page_count: number | null
  llm_score: number | null
  llm_obsolete: boolean | null
  llm_verdict: string | null
  lighthouse_scores: LighthouseScores | null
  lighthouse_seo: LighthouseSeo | null
  lighthouse_remarks: LighthouseRemark[] | null
  analyzed_at: string
}

export interface ContactRead {
  id: number
  type: string  // "email" | "phone"
  value: string
  source: string  // "osm" | "page" | "rne"
  nature: string | null
  suspicious: boolean | null
  warnings: string[]
  created_at: string
}

export interface DirigeantRead {
  nom: string | null
  prenoms: string[]
  role: string | null
  role_label: string
  beneficiaire_effectif: boolean | null
  diffusion_commerciale: boolean
}

export interface CompanyRead {
  id: number
  siren: string
  denomination: string | null
  type_personne: string | null
  forme_juridique: string | null
  code_ape: string | null
  code_ape_label: string
  date_creation: string | null
  commune: string | null
  code_postal: string | null
  diffusion_insee: boolean
  noms_de_domaine: DomainEntry[]
  source_insee: boolean
  source_rne: boolean
  created_at: string
  updated_at: string
  websites: WebsiteRead[]
  contacts: ContactRead[]
  analysis: AnalysisRead | null
}

export interface CompanyDetail extends CompanyRead {
  dirigeants: DirigeantRead[]
}

export interface IngestResult { fetched: number; processed: number; skipped: number }
export interface EnrichResult { enriched: number; candidates: number; skipped: number }
export interface WebsiteDetectResult { processed: number; candidates_probed: number }
export interface FilterResult { deleted: number }
export interface EnrichSirenResult {
  siren: string
  rne_ok: boolean
  rne_dirigeants: number
  osm_ok: boolean
  osm_domain: string | null
  osm_contacts: number
}
export interface AnalyzeResult { done: number; not_owned: number; indeterminate: number; no_site: number }
