import type { CompanyRead, OpportunityKey, WebStatus } from './types/index'

export function webStatusOf(c: CompanyRead): WebStatus {
  const selected = c.websites?.find(w => w.is_selected)
  if (selected) {
    return selected.http_status !== null && selected.http_status < 400 ? 'site' : 'unknown'
  }
  return (c.websites?.length || c.noms_de_domaine?.length) ? 'unknown' : 'none'
}

export function selectedDomain(c: CompanyRead): string | null {
  return c.websites.find(w => w.is_selected)?.domain ?? c.noms_de_domaine[0]?.domain ?? null
}

// llm_score is 1–10 (10 = modern quality site).
// Opportunity is the inverse: a bad site = high opportunity for a web agency.
export function oppOf(c: CompanyRead): number {
  if (c.analysis?.llm_score != null) {
    return Math.max(0, Math.min(100, 110 - c.analysis.llm_score * 10))
  }
  const lh = c.analysis?.lighthouse_scores
  if (lh) {
    const perf = lh.performance ?? 50
    const seo = lh.seo ?? 50
    // High quality = low opportunity for a web agency (they don't need us)
    return Math.max(0, Math.min(100, Math.round(110 - (perf + seo) / 2)))
  }
  return webStatusOf(c) === 'none' ? 90 : 50
}

export function oppKeyOf(opp: number): OpportunityKey {
  return opp >= 75 ? 'forte' : opp >= 45 ? 'moyenne' : 'faible'
}

export interface OppColors { text: string; dot: string; bg: string; border: string }

export function oppColors(key: OpportunityKey): OppColors {
  return {
    forte:   { text: '#b8410e', dot: '#e8590c', bg: '#fdeee6', border: '#f6d4c2' },
    moyenne: { text: '#9a6b00', dot: '#e0a400', bg: '#fdf6e3', border: '#f0e4b8' },
    faible:  { text: '#0b7a6e', dot: '#12a594', bg: '#e9f6f0', border: '#cfe9e1' },
  }[key]
}

export interface WebMeta { text: string; color: string; bg: string; border: string; dot: string; dashed: boolean }

export function webMeta(web: WebStatus): WebMeta {
  return {
    site:    { text: 'Site détecté', color: '#0b7a6e', bg: '#eaf6f2', border: '#cfe9e1', dot: '#12a594', dashed: false },
    none:    { text: 'Pas de site',  color: '#5c6363', bg: '#f0f1f2', border: '#e6e8e8', dot: '#a4abab', dashed: false },
    unknown: { text: 'À vérifier',  color: '#8a9090', bg: '#ffffff', border: '#d4d8d8', dot: '#c4caca', dashed: true  },
  }[web]
}

// Site quality score (0–100, higher = better site). Inverse of opportunity.
export function siteScoreOf(c: CompanyRead): number | null {
  if (c.analysis?.llm_score != null) return c.analysis.llm_score * 10
  return null
}

export function gradeOf(score: number | null): string {
  if (score === null) return '—'
  if (score >= 90) return 'A'
  if (score >= 78) return 'B'
  if (score >= 62) return 'C'
  if (score >= 48) return 'D'
  if (score >= 34) return 'E'
  return 'F'
}

export interface GradeColors { text: string; bg: string; border: string }

export function gradeColors(g: string): GradeColors {
  if (g === 'A' || g === 'B') return { text: '#0b7a6e', bg: '#e9f6f0', border: '#cfe9e1' }
  if (g === 'C' || g === 'D') return { text: '#9a6b00', bg: '#fdf6e3', border: '#f0e4b8' }
  return { text: '#b8410e', bg: '#fdeee6', border: '#f6d4c2' }
}

export function lhColor(v: number): string {
  return v >= 90 ? '#0b7a6e' : v >= 50 ? '#9a6b00' : '#b8410e'
}

export function lhBg(v: number): string {
  return v >= 90 ? '#12a594' : v >= 50 ? '#e0a400' : '#e8590c'
}

export function initialsOf(nom: string): string {
  return nom.split(' ').filter(Boolean).slice(0, 2).map(s => s[0]).join('').toUpperCase()
}

export function verdictTextOf(c: CompanyRead): string {
  const web = webStatusOf(c)
  if (web === 'none') return 'Pas de site'
  if (!c.analysis) return 'À vérifier'
  const key = oppKeyOf(oppOf(c))
  return key === 'forte' ? 'À refaire' : key === 'moyenne' ? 'Correct' : 'Récent'
}

// forme_juridique INSEE code → short abbreviation
const FORME_ABBR: Record<string, string> = {
  '1000': 'EI',   '2110': 'GAEC',  '5202': 'SNC',   '5306': 'GIE',
  '5410': 'SARL', '5415': 'EARL',  '5422': 'EURL',  '5498': 'SARL',
  '5499': 'SARL', '5522': 'SA',    '5599': 'SA',    '5705': 'SAS',
  '5710': 'SAS',  '5720': 'SASU',  '6534': 'SCPI',  '6541': 'SCI',
  '6616': 'SELARL', '6618': 'SELAS', '6629': 'SEL',
  '9210': 'Asso.', '9220': 'Asso.', '9240': 'Asso.', '9300': 'Fond.',
}

export function formeAbbr(code: string | null): string {
  if (!code) return '—'
  return FORME_ABBR[code] ?? code
}

export interface VerdictMeta { label: string; color: string; bg: string; border: string }

export function ownershipVerdictMeta(verdict: string | null): VerdictMeta {
  switch (verdict) {
    case 'confirmed':    return { label: 'Propriété confirmée',    color: '#0b7a6e', bg: '#e9f6f0', border: '#cfe9e1' }
    case 'probable':     return { label: 'Propriété probable',     color: '#9a6b00', bg: '#fdf6e3', border: '#f0e4b8' }
    case 'rejected':     return { label: 'Propriété rejetée',      color: '#b8410e', bg: '#fdeee6', border: '#f6d4c2' }
    case 'indeterminate':return { label: 'Ownership indéterminé',  color: '#5c6363', bg: '#f0f1f2', border: '#e6e8e8' }
    default:             return { label: 'Ownership inconnu',      color: '#5c6363', bg: '#f0f1f2', border: '#e6e8e8' }
  }
}

// Parse Wayback YYYYMMDD → age in years relative to now
export function ageFromWayback(wayback: string | null): number | null {
  if (!wayback || wayback.length < 4) return null
  const year = parseInt(wayback.slice(0, 4), 10)
  if (isNaN(year)) return null
  return new Date().getFullYear() - year
}
