<script setup lang="ts">
import { computed, ref } from 'vue'
import { useStore } from '../composables/useStore'
import {
  oppOf, oppKeyOf, oppColors, verdictTextOf,
  initialsOf, lhColor, lhBg, webStatusOf, selectedDomain,
  formeAbbr, ageFromWayback, ownershipVerdictMeta,
} from '../utils'
import type { LighthouseSeo, WebsiteRead } from '../types/index'

const { state, goList, toggleBasket, enrichRNE, analyzeOne } = useStore()

const company = computed(() => state.detail)

const oc = computed(() => company.value ? oppColors(oppKeyOf(oppOf(company.value))) : null)
const inBasket    = computed(() => !!company.value && state.basket.includes(company.value.siren))
const rneSynced   = computed(() => !!company.value && state.enrichedIds.includes(company.value.siren))
const rneLoading  = computed(() => !!company.value && state.enrichingId === company.value.siren)
const verdictText = computed(() => company.value ? verdictTextOf(company.value) : '')

const an = computed(() => company.value?.analysis ?? null)

const ageYears = computed(() => an.value ? ageFromWayback(an.value.wayback_first_seen) : null)

const ageHint = computed(() => {
  const y = ageYears.value
  if (y === null) return ''
  if (y >= 6) return 'Site nettement daté — signal commercial fort.'
  if (y >= 3) return "Site dans la moyenne d'âge — opportunité modérée."
  return 'Site récent — faible opportunité de refonte.'
})

const conformiteMeta = computed(() => {
  if (!company.value) return null
  if (!(company.value.contacts?.length)) return null
  if (!company.value.diffusion_insee) {
    return { text: 'Opposition à la prospection', color: '#b8410e', bg: '#fdeee6', border: '#f6d4c2' }
  }
  return { text: 'Contactable · conformité OK', color: '#0b7a6e', bg: '#e9f6f0', border: '#cfe9e1' }
})

const sortedContacts = computed(() => {
  if (!company.value?.contacts?.length) return []
  return [...company.value.contacts].sort((a, b) => {
    const aReliable = a.source === 'page' && !a.suspicious ? 0 : 1
    const bReliable = b.source === 'page' && !b.suspicious ? 0 : 1
    return aReliable - bReliable
  })
})

function dirigeantName(d: { nom: string | null; prenoms: string[] }): string {
  return [...d.prenoms, d.nom].filter(Boolean).join(' ')
}

function domainHref(w: WebsiteRead): string {
  return w.final_url ?? `https://${w.domain}`
}

// ── Lighthouse helpers ────────────────────────────────────────────────────────

const lhScores = computed(() => an.value?.lighthouse_scores ?? null)
const lhSeo    = computed(() => an.value?.lighthouse_seo    ?? null)
const lhRemarks = computed(() => an.value?.lighthouse_remarks ?? [])

const LH_CATEGORIES = [
  { key: 'performance',    label: 'Performance' },
  { key: 'accessibility',  label: 'Accessibilité' },
  { key: 'best_practices', label: 'Bonnes pratiques' },
  { key: 'seo',           label: 'SEO' },
] as const

const LH_METRICS = [
  { key: 'first_contentful_paint',  label: 'First Contentful Paint' },
  { key: 'largest_contentful_paint', label: 'Largest Contentful Paint' },
  { key: 'total_blocking_time',     label: 'Total Blocking Time' },
  { key: 'cumulative_layout_shift', label: 'Cumul. Layout Shift' },
  { key: 'speed_index',             label: 'Speed Index' },
]

const LH_SEO_CHECKS = [
  { key: 'meta_description',  label: 'Méta-description' },
  { key: 'document_title',    label: 'Titre de page' },
  { key: 'canonical',         label: 'Balise canonical' },
  { key: 'robots_txt',        label: 'Robots.txt' },
  { key: 'is_crawlable',      label: 'Page indexable' },
  { key: 'structured_data',   label: 'Données structurées' },
  { key: 'image_alt',         label: 'Textes alternatifs' },
  { key: 'http_status_code',  label: 'Code HTTP 2xx' },
  { key: 'font_size',         label: 'Taille de police' },
  { key: 'hreflang',          label: 'Balises hreflang' },
]

function seoPass(key: string): boolean | null {
  const point = lhSeo.value?.[key as keyof LighthouseSeo] as { pass?: boolean | null } | undefined
  return point?.pass ?? null
}

function seoIcon(key: string): string {
  const p = seoPass(key)
  return p === true ? '✓' : p === false ? '✗' : '·'
}

function seoColor(key: string): string {
  const p = seoPass(key)
  return p === true ? '#0b7a6e' : p === false ? '#b8410e' : '#c4caca'
}

const CAT_BADGE: Record<string, { bg: string; color: string; border: string }> = {
  performance:      { bg: '#eef2ff', color: '#4338ca', border: '#c7d2fe' },
  accessibility:    { bg: '#f0fdf4', color: '#166534', border: '#bbf7d0' },
  'best-practices': { bg: '#fffbeb', color: '#92400e', border: '#fde68a' },
  seo:              { bg: '#fdf4ff', color: '#7e22ce', border: '#e9d5ff' },
}
const CAT_LABEL: Record<string, string> = {
  performance: 'Perf', accessibility: 'Access.', 'best-practices': 'Pratiques', seo: 'SEO',
}

function catBadge(cat: string) {
  const c = CAT_BADGE[cat] ?? { bg: '#f0f1f2', color: '#5c6363', border: '#e6e8e8' }
  return { background: c.bg, color: c.color, border: `1px solid ${c.border}` }
}

// ── Ownership signals ─────────────────────────────────────────────────────────

const SIGNAL_LABELS: Record<string, string> = {
  siren:               'SIREN',
  denomination:        'Dénomination',
  denomination_approx: 'Dénomination approx.',
  code_postal:         'Code postal',
  commune:             'Commune',
  dirigeant:           'Dirigeant',
  domain_name:         'Domaine',
}

const SKIP_SIGNAL_KEYS = new Set(['verdict', 'score', 'reason', 'source'])

const ownershipVerdict = computed(() => {
  const v = (an.value?.ownership_signals as Record<string, unknown> | null)?.verdict
  return typeof v === 'string' ? v : null
})

const ownershipVerdictStyle = computed(() => ownershipVerdictMeta(ownershipVerdict.value))

const ownershipBoolSignals = computed(() => {
  const signals = an.value?.ownership_signals as Record<string, unknown> | null
  if (!signals) return []
  return Object.entries(signals)
    .filter(([k, v]) => !SKIP_SIGNAL_KEYS.has(k) && typeof v === 'boolean')
    .map(([k, v]) => ({ key: k, label: SIGNAL_LABELS[k] ?? k, value: v as boolean }))
})

// ── Internal links toggle ─────────────────────────────────────────────────────

const showAllLinks = ref(false)
</script>

<template>
  <!-- Loading -->
  <main v-if="state.detailLoading" class="max-w-[1080px] mx-auto px-7 pt-[22px] pb-20 flex items-center justify-center min-h-[400px]">
    <div class="flex flex-col items-center gap-3">
      <div class="w-6 h-6 rounded-full border-[3px] border-[#cfe9e1] border-t-[#0e9384] animate-pe-spin"></div>
      <p class="text-[13px] text-[#8a9090]">Chargement…</p>
    </div>
  </main>

  <!-- Not found -->
  <main v-else-if="!company" class="max-w-[1080px] mx-auto px-7 pt-[22px] pb-20">
    <button class="bg-transparent border-none text-[#5c6363] text-[13px] font-medium p-0 mb-[14px]" @click="goList()">‹ Retour</button>
    <p class="text-[13px] text-[#8a9090]">Entreprise introuvable.</p>
  </main>

  <!-- Detail -->
  <main v-else class="max-w-[1080px] mx-auto px-7 pt-[22px] pb-20">

    <!-- Back -->
    <button
      class="bg-transparent border-none text-[#5c6363] text-[13px] font-medium p-0 mb-[14px]"
      @click="goList()"
    >‹ Retour à la liste</button>

    <!-- Company header -->
    <div class="flex items-start justify-between gap-6 flex-wrap mb-[22px]">
      <div class="min-w-0">
        <div class="flex items-center gap-[11px] flex-wrap">
          <h1 class="m-0 text-[24px] font-semibold tracking-[-0.02em]">{{ company.denomination ?? company.siren }}</h1>
          <span class="text-[12px] font-semibold text-[#5c6363] bg-[#f0f1f2] border border-[#e6e8e8] px-[9px] py-[3px] rounded-[7px]">
            {{ formeAbbr(company.forme_juridique) }}
          </span>
          <span
            v-if="company.analysis && oc"
            class="inline-flex items-center gap-[6px] px-[9px] py-[3px] rounded-full text-[12px] font-semibold"
            :style="{ background: oc.bg, color: oc.text, border: `1px solid ${oc.border}` }"
          >
            <span class="w-[6px] h-[6px] rounded-full flex-shrink-0" :style="{ background: oc.dot }"></span>
            {{ verdictText }}
          </span>
          <span
            v-else
            class="inline-flex items-center gap-[6px] text-[12px] font-medium text-[#a4abab] bg-[#f6f7f7] border border-dashed border-[#e0e3e3] px-[9px] py-[3px] rounded-[7px]"
          >
            Non analysé
          </span>
        </div>
        <p class="mt-[7px] mb-0 text-[13.5px] text-[#8a9090]">
          {{ company.code_ape ?? 'N/A' }}<template v-if="company.code_ape_label"> — {{ company.code_ape_label }}</template> · {{ company.commune ?? '—' }} ({{ company.code_postal ?? '' }})
        </p>
      </div>

      <!-- Action buttons -->
      <div class="flex items-center gap-[10px]">
        <button
          class="border rounded-[8px] px-[14px] py-[9px] text-[13px] font-semibold"
          :class="{ 'opacity-60 pointer-events-none': rneLoading }"
          :style="{
            background: '#fff',
            border: `1px solid ${rneSynced ? '#cfe9e1' : '#e0e3e3'}`,
            color: rneSynced ? '#0b7a6e' : '#3a4040',
          }"
          @click="enrichRNE(company!.siren)"
        >
          {{ rneLoading ? 'Synchronisation RNE…' : rneSynced ? '✓ RNE synchronisé' : 'Enrichir via RNE' }}
        </button>
        <button
          class="border rounded-[8px] px-[14px] py-[9px] text-[13px] font-semibold"
          :style="{
            background: inBasket ? '#e9f6f0' : '#fff',
            border: `1px solid ${inBasket ? '#cfe9e1' : '#e0e3e3'}`,
            color: inBasket ? '#0b7a6e' : '#3a4040',
          }"
          @click="toggleBasket(company!.siren)"
        >
          {{ inBasket ? '✓ Dans le panier' : 'Ajouter au panier' }}
        </button>
      </div>
    </div>

    <!-- 2-col grid -->
    <div class="grid grid-cols-2 gap-4">

      <!-- Identité -->
      <section class="bg-white border border-[#e6e8e8] rounded-[12px] p-[18px_20px]">
        <div class="flex items-center justify-between mb-[14px]">
          <h2 class="m-0 text-[12px] font-semibold text-[#8a9090] uppercase tracking-[.05em]">Identité</h2>
          <span
            v-if="rneSynced"
            class="text-[10.5px] font-semibold text-[#0b7a6e] bg-[#e9f6f0] border border-[#cfe9e1] px-2 py-[2px] rounded-[6px]"
          >
            RNE · à jour
          </span>
        </div>
        <div class="grid gap-[10px_18px] text-[13px]" style="grid-template-columns: auto 1fr;">
          <span class="text-[#a4abab]">SIREN</span>
          <span class="font-mono text-[#1a1d1d]">{{ company.siren }}</span>
          <span class="text-[#a4abab]">Localisation</span>
          <span class="text-[#1a1d1d]">{{ [company.commune, company.code_postal].filter(Boolean).join(' — ') || '—' }}</span>
          <span class="text-[#a4abab]">Forme juridique</span>
          <span class="text-[#1a1d1d]">{{ company.forme_juridique ?? '—' }}</span>
          <span class="text-[#a4abab]">Création</span>
          <span class="text-[#1a1d1d]">{{ company.date_creation ?? '—' }}</span>
          <span class="text-[#a4abab]">Code APE</span>
          <span class="text-[#1a1d1d]">
            <span class="font-mono">{{ company.code_ape ?? '—' }}</span>
            <span v-if="company.code_ape_label" class="text-[#8a9090] ml-[6px]">{{ company.code_ape_label }}</span>
          </span>
          <span class="text-[#a4abab]">Diffusion INSEE</span>
          <span :style="{ color: company.diffusion_insee ? '#0b7a6e' : '#b8410e' }">
            {{ company.diffusion_insee ? 'Oui' : 'Non (opt-out)' }}
          </span>
        </div>
      </section>

      <!-- Dirigeants -->
      <section class="bg-white border border-[#e6e8e8] rounded-[12px] p-[18px_20px]">
        <h2 class="m-0 mb-[14px] text-[12px] font-semibold text-[#8a9090] uppercase tracking-[.05em]">Dirigeants</h2>
        <div v-if="company.dirigeants?.length" class="flex flex-col gap-[11px]">
          <div v-for="(d, i) in company.dirigeants" :key="i" class="flex items-center gap-[11px]">
            <div class="w-8 h-8 rounded-full bg-[#f0f1f2] border border-[#e6e8e8] flex items-center justify-center text-[12px] font-semibold text-[#5c6363]">
              {{ initialsOf(dirigeantName(d)) }}
            </div>
            <div>
              <div class="text-[13.5px] font-semibold">
                {{ dirigeantName(d) }}
              </div>
              <div class="text-[12px] text-[#8a9090]">{{ d.role_label || d.role || '' }}</div>
            </div>
          </div>
        </div>
        <div v-else class="p-[14px] bg-[#fafbfb] border border-dashed border-[#e0e3e3] rounded-[9px] text-[12.5px] text-[#a4abab] text-center">
          Aucun dirigeant renseigné · enrichir via RNE pour obtenir les données.
        </div>
      </section>

      <!-- Présence web (full width) -->
      <section class="bg-white border border-[#e6e8e8] rounded-[12px] p-[18px_20px] col-span-2">
        <div class="flex items-center justify-between mb-[14px]">
          <h2 class="m-0 text-[12px] font-semibold text-[#8a9090] uppercase tracking-[.05em]">Présence web — domaines candidats</h2>
          <span
            v-if="!company.analysis && webStatusOf(company) !== 'none'"
            class="text-[11px] text-[#9a6b00] bg-[#fdf6e3] border border-[#f0e4b8] px-[9px] py-[3px] rounded-[7px] font-medium"
          >
            Présomption — non confirmée tant que non analysée
          </span>
        </div>

        <!-- Websites list -->
        <div v-if="company.websites?.length" class="flex flex-col gap-[9px]">
          <div
            v-for="w in company.websites"
            :key="w.domain"
            class="flex items-center justify-between gap-3 px-[13px] py-[11px] rounded-[9px]"
            :style="{
              border: `1px solid ${w.is_selected ? '#cfe9e1' : '#eceeef'}`,
              background: w.is_selected ? '#f6fcfa' : '#fafbfb',
            }"
          >
            <div class="flex items-center gap-[10px] min-w-0 flex-1">
              <span
                v-if="w.is_selected"
                class="text-[10px] font-bold text-[#0b7a6e] bg-[#e9f6f0] border border-[#cfe9e1] px-[7px] py-[2px] rounded-[6px] uppercase tracking-[.04em]"
              >
                Retenu
              </span>
              <a
                :href="domainHref(w)"
                target="_blank"
                rel="noopener noreferrer"
                class="font-mono text-[13.5px] font-medium text-[#0b7a6e] whitespace-nowrap overflow-hidden text-ellipsis hover:underline"
              >
                {{ w.domain }}
              </a>
            </div>
            <div class="flex items-center gap-[7px]">
              <span
                v-for="[label, ok] in [['DNS', w.dns_resolved], ['HTTPS', w.is_https], ['OK', w.http_status !== null && w.http_status < 400]]"
                :key="label as string"
                class="text-[10.5px] font-semibold px-[7px] py-[2px] rounded-[6px]"
                :style="{
                  background: ok ? '#e9f6f0' : '#f4f5f5',
                  color: ok ? '#0b7a6e' : '#c4caca',
                  border: `1px solid ${ok ? '#cfe9e1' : '#eceeef'}`,
                }"
              >
                {{ label }}
              </span>
              <span
                class="font-mono text-[12.5px] font-medium min-w-[40px] text-right"
                :style="{ color: lhColor(w.confidence) }"
              >
                {{ w.confidence }}%
              </span>
            </div>
          </div>
        </div>

        <!-- No websites -->
        <div v-else class="flex items-center gap-3 p-4 bg-[#fafbfb] border border-dashed border-[#e0e3e3] rounded-[9px]">
          <div class="w-[34px] h-[34px] rounded-[8px] bg-[#f0f1f2] flex items-center justify-center text-[#a4abab] text-[16px] flex-shrink-0">⌀</div>
          <div>
            <div class="text-[13px] font-semibold text-[#5c6363]">Aucun domaine détecté</div>
            <div class="text-[12px] text-[#a4abab]">Forte opportunité : refonte = création complète de présence web.</div>
          </div>
        </div>
      </section>

      <!-- Audit section (full width) -->
      <section class="col-span-2 flex flex-col gap-[14px]">
        <h2 class="m-0 text-[12px] font-semibold text-[#8a9090] uppercase tracking-[.05em]">Audit du site</h2>

        <!-- Not analyzed CTA -->
        <div v-if="!company.analysis" class="bg-white border border-[#e6e8e8] rounded-[12px] px-6 py-7 text-center">
          <div class="w-[42px] h-[42px] rounded-[10px] bg-[#f0f1f2] border border-dashed border-[#d4d8d8] mx-auto mb-[14px]"></div>
          <p class="m-0 mx-auto mb-[14px] max-w-[440px] text-[13px] text-[#8a9090] leading-[1.55]">
            Cette entreprise n'a pas encore été analysée. Lancez l'audit du site pour confirmer le signal d'opportunité.
          </p>
          <button
            class="bg-[#0e9384] text-white border-none rounded-[8px] px-[18px] py-[10px] text-[13px] font-semibold"
            :class="{ 'opacity-60 pointer-events-none': state.analyzing }"
            @click="analyzeOne(company!.siren)"
          >
            {{ state.analyzing ? 'Analyse en cours…' : 'Lancer l\'analyse de ce site' }}
          </button>
        </div>

        <!-- Analyzed results -->
        <template v-else-if="an && oc">

          <!-- Verdict banner -->
          <div
            class="flex items-center justify-between gap-6 flex-wrap px-[26px] py-6 rounded-[14px]"
            :style="{ background: oc.bg, border: `1px solid ${oc.border}` }"
          >
            <div class="min-w-0">
              <div class="text-[11px] font-semibold uppercase tracking-[.06em] opacity-70" :style="{ color: oc.text }">
                Verdict de l'audit
              </div>
              <div class="mt-1 mb-[6px] text-[24px] font-semibold tracking-[-0.02em]" :style="{ color: oc.text }">
                {{ verdictText }}
              </div>
              <div class="text-[13px] text-[#3a4040]">
                <span class="font-mono">{{ selectedDomain(company) || 'aucun domaine' }}</span>
              </div>
            </div>

            <!-- Lighthouse mini-scores -->
            <div v-if="lhScores" class="flex items-center gap-[10px]">
              <div
                v-for="cat in LH_CATEGORIES"
                :key="cat.key"
                class="flex flex-col items-center gap-[4px] px-[10px] py-[8px] rounded-[9px] bg-white bg-opacity-60 border border-white border-opacity-80 min-w-[52px]"
              >
                <span class="font-mono text-[18px] font-semibold leading-none" :style="{ color: lhColor(lhScores[cat.key] ?? 0) }">
                  {{ lhScores[cat.key] ?? '—' }}
                </span>
                <span class="text-[9.5px] font-semibold uppercase tracking-[.04em] text-[#8a9090]">{{ cat.label }}</span>
              </div>
            </div>
            <div v-else class="text-[12.5px] font-medium text-[#a4abab] italic">
              Audit Lighthouse non disponible
            </div>
          </div>

          <!-- Ownership nuancée -->
          <section class="bg-white border border-[#e6e8e8] rounded-[12px] p-[18px_20px]">
            <h3 class="m-0 mb-[14px] text-[12px] font-semibold text-[#8a9090] uppercase tracking-[.05em]">Propriété du site</h3>
            <div class="flex items-start gap-4 flex-wrap">
              <!-- Verdict badge -->
              <span
                class="inline-flex items-center text-[12px] font-semibold px-[10px] py-[5px] rounded-[7px] border flex-shrink-0"
                :style="{
                  background: ownershipVerdictStyle.bg,
                  color: ownershipVerdictStyle.color,
                  border: `1px solid ${ownershipVerdictStyle.border}`,
                }"
              >
                {{ ownershipVerdictStyle.label }}
              </span>

              <!-- Boolean signals -->
              <div v-if="ownershipBoolSignals.length > 0" class="flex flex-wrap gap-[6px]">
                <span
                  v-for="sig in ownershipBoolSignals"
                  :key="sig.key"
                  class="inline-flex items-center gap-[5px] text-[11.5px] font-medium px-[8px] py-[4px] rounded-[6px] border"
                  :style="sig.value
                    ? { background: '#e9f6f0', color: '#0b7a6e', border: '1px solid #cfe9e1' }
                    : { background: '#f4f5f5', color: '#a4abab', border: '1px solid #e6e8e8' }"
                >
                  <span>{{ sig.value ? '✓' : '✗' }}</span>
                  <span>{{ sig.label }}</span>
                </span>
              </div>
              <span v-else class="text-[12.5px] text-[#a4abab]">Aucun signal détaillé disponible.</span>
            </div>
          </section>

          <!-- Signaux d'opportunité -->
          <section class="bg-white border border-[#e6e8e8] rounded-[12px] p-[18px_20px]">
            <h3 class="m-0 mb-[14px] text-[12px] font-semibold text-[#8a9090] uppercase tracking-[.05em]">Signaux d'opportunité</h3>

            <!-- Fact grid -->
            <div class="grid grid-cols-2 gap-x-8 gap-y-[10px] text-[13px] mb-[16px]">
              <div class="flex items-baseline gap-3">
                <span class="text-[#a4abab] min-w-[120px] flex-shrink-0">Âge du site</span>
                <span class="font-semibold text-[#1a1d1d]">
                  {{ ageYears !== null ? `${ageYears} an${ageYears > 1 ? 's' : ''} (depuis ${an.wayback_first_seen!.slice(0, 4)})` : '—' }}
                </span>
              </div>
              <div class="flex items-baseline gap-3">
                <span class="text-[#a4abab] min-w-[120px] flex-shrink-0">Dernière MAJ</span>
                <span class="font-semibold text-[#1a1d1d]">{{ an.sitemap_last_modified ? an.sitemap_last_modified.slice(0, 10) : 'inconnue' }}</span>
              </div>
              <div class="flex items-baseline gap-3">
                <span class="text-[#a4abab] min-w-[120px] flex-shrink-0">Nb de pages</span>
                <span class="font-semibold text-[#1a1d1d]">{{ an.sitemap_page_count ?? '—' }}</span>
              </div>
              <div class="flex items-baseline gap-3">
                <span class="text-[#a4abab] min-w-[120px] flex-shrink-0">Performance</span>
                <span
                  class="font-semibold"
                  :style="{ color: an.lighthouse_scores?.performance != null ? lhColor(an.lighthouse_scores.performance) : '#a4abab' }"
                >
                  {{ an.lighthouse_scores?.performance ?? 'non mesuré' }}
                </span>
              </div>
            </div>

            <!-- Age hint -->
            <div v-if="ageHint" class="text-[12px] leading-[1.5] px-3 py-[9px] rounded-[8px] font-medium mb-[16px]" :style="{ background: oc.bg, color: oc.text }">
              {{ ageHint }}
            </div>

            <!-- Tech stack with obsolete markers -->
            <div>
              <div class="text-[11px] font-semibold text-[#8a9090] uppercase tracking-[.05em] mb-[8px]">Technologies détectées</div>
              <div v-if="(an.tech_stack ?? []).length > 0" class="flex flex-wrap gap-[6px]">
                <span
                  v-for="tech in an.tech_stack"
                  :key="tech"
                  class="inline-flex items-center gap-[5px] text-[12px] font-semibold px-[8px] py-[4px] rounded-[6px]"
                  :style="(an.obsolete_tech ?? []).includes(tech)
                    ? { background: '#fdeee6', color: '#b8410e', border: '1px solid #f6d4c2' }
                    : { background: '#f0f1f2', color: '#5c6363', border: '1px solid #e6e8e8' }"
                >
                  {{ tech }}
                  <span v-if="(an.obsolete_tech ?? []).includes(tech)" class="font-normal opacity-75">· obsolète</span>
                </span>
              </div>
              <span v-else class="text-[12.5px] text-[#a4abab]">Aucune technologie détectée.</span>
            </div>
          </section>

          <!-- Liens du site -->
          <section class="bg-white border border-[#e6e8e8] rounded-[12px] p-[18px_20px]">
            <h3 class="m-0 mb-[14px] text-[12px] font-semibold text-[#8a9090] uppercase tracking-[.05em]">Liens du site</h3>

            <!-- Checklist + provider -->
            <div class="flex items-center gap-[10px] flex-wrap mb-[14px]">
              <span
                class="inline-flex items-center gap-[5px] text-[11.5px] font-medium px-[8px] py-[4px] rounded-[6px] border"
                :style="an.has_legal_page
                  ? { background: '#e9f6f0', color: '#0b7a6e', border: '1px solid #cfe9e1' }
                  : { background: '#fdeee6', color: '#b8410e', border: '1px solid #f6d4c2' }"
              >
                {{ an.has_legal_page ? '✓' : '✗' }} Mentions légales
              </span>
              <span
                class="inline-flex items-center gap-[5px] text-[11.5px] font-medium px-[8px] py-[4px] rounded-[6px] border"
                :style="an.has_contact_info
                  ? { background: '#e9f6f0', color: '#0b7a6e', border: '1px solid #cfe9e1' }
                  : { background: '#fdeee6', color: '#b8410e', border: '1px solid #f6d4c2' }"
              >
                {{ an.has_contact_info ? '✓' : '✗' }} Page contact
              </span>
              <span
                v-if="an.provider_hint"
                class="inline-flex items-center gap-[5px] text-[11.5px] font-medium px-[8px] py-[4px] rounded-[6px] bg-[#f0f1f2] text-[#5c6363] border border-[#e6e8e8]"
              >
                Hébergeur · {{ an.provider_hint }}
              </span>
            </div>

            <!-- External links -->
            <div class="mb-[14px]">
              <div class="text-[11px] font-semibold text-[#8a9090] uppercase tracking-[.05em] mb-[8px]">
                Liens externes ({{ (an.external_links ?? []).length }})
              </div>
              <div v-if="(an.external_links ?? []).length > 0" class="flex flex-col gap-[5px]">
                <a
                  v-for="url in an.external_links"
                  :key="url"
                  :href="url"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="font-mono text-[12.5px] text-[#0b7a6e] hover:underline truncate"
                >
                  {{ url }}
                </a>
              </div>
              <span v-else class="text-[12.5px] text-[#a4abab]">Aucun lien externe détecté.</span>
            </div>

            <!-- Internal links -->
            <div>
              <div class="flex items-center justify-between mb-[8px]">
                <div class="text-[11px] font-semibold text-[#8a9090] uppercase tracking-[.05em]">
                  Liens internes ({{ (an.internal_links ?? []).length }})
                </div>
                <button
                  v-if="(an.internal_links ?? []).length > 0"
                  class="text-[11.5px] text-[#0b7a6e] bg-transparent border-none cursor-pointer font-medium p-0"
                  @click="showAllLinks = !showAllLinks"
                >
                  {{ showAllLinks ? 'Masquer' : 'Voir tous' }}
                </button>
              </div>
              <div v-if="showAllLinks && (an.internal_links ?? []).length > 0" class="flex flex-col gap-[4px] max-h-[220px] overflow-y-auto pr-1">
                <a
                  v-for="url in an.internal_links"
                  :key="url"
                  :href="url"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="font-mono text-[11.5px] text-[#5c6363] hover:underline truncate"
                >
                  {{ url }}
                </a>
              </div>
              <span v-else-if="(an.internal_links ?? []).length === 0" class="text-[12.5px] text-[#a4abab]">Aucun lien interne détecté.</span>
            </div>
          </section>

          <!-- Lighthouse audit -->
          <section v-if="lhScores" class="bg-white border border-[#e6e8e8] rounded-[12px] p-[18px_20px]">
            <h3 class="m-0 mb-[18px] text-[12px] font-semibold text-[#8a9090] uppercase tracking-[.05em]">Audit Lighthouse</h3>

            <!-- 4 score gauges -->
            <div class="grid grid-cols-4 gap-3 mb-5">
              <div v-for="cat in LH_CATEGORIES" :key="cat.key" class="flex flex-col items-center gap-[6px] px-3 py-[14px] rounded-[10px] bg-[#fafbfb] border border-[#f0f1f2]">
                <div class="text-[30px] font-mono font-semibold leading-none" :style="{ color: lhColor(lhScores[cat.key] ?? 0) }">
                  {{ lhScores[cat.key] ?? '—' }}
                </div>
                <div class="text-[10.5px] font-semibold text-[#8a9090] uppercase tracking-[.04em]">{{ cat.label }}</div>
                <div class="w-full h-[4px] rounded-full bg-[#e6e8e8] overflow-hidden">
                  <div class="h-full rounded-full transition-all" :style="{ width: (lhScores[cat.key] ?? 0) + '%', background: lhBg(lhScores[cat.key] ?? 0) }"></div>
                </div>
              </div>
            </div>

            <!-- Core Web Vitals + SEO checklist -->
            <div class="grid grid-cols-2 gap-5 mb-5">
              <div>
                <div class="text-[11px] font-semibold text-[#8a9090] uppercase tracking-[.05em] mb-[10px]">Core Web Vitals</div>
                <div class="flex flex-col gap-[8px]">
                  <div v-for="m in LH_METRICS" :key="m.key" class="flex items-center justify-between gap-3">
                    <span class="text-[12.5px] text-[#5c6363]">{{ m.label }}</span>
                    <span
                      class="font-mono text-[12.5px] font-semibold"
                      :style="{ color: lhColor(lhSeo?.metrics?.[m.key]?.score ?? 0) }"
                    >{{ lhSeo?.metrics?.[m.key]?.display_value ?? '—' }}</span>
                  </div>
                </div>
              </div>

              <div>
                <div class="text-[11px] font-semibold text-[#8a9090] uppercase tracking-[.05em] mb-[10px]">Points SEO importants</div>
                <div class="flex flex-col gap-[8px]">
                  <div v-for="s in LH_SEO_CHECKS" :key="s.key" class="flex items-center gap-[9px]">
                    <span class="text-[13px] font-semibold w-4 flex-shrink-0" :style="{ color: seoColor(s.key) }">{{ seoIcon(s.key) }}</span>
                    <span class="text-[12.5px] text-[#3a4040]">{{ s.label }}</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- Remarques importantes -->
            <div v-if="lhRemarks.length > 0">
              <div class="text-[11px] font-semibold text-[#8a9090] uppercase tracking-[.05em] mb-[10px]">Remarques importantes</div>
              <div class="flex flex-col">
                <div
                  v-for="r in lhRemarks"
                  :key="r.id"
                  class="flex items-start gap-[11px] py-[10px] border-b border-[#f4f5f5] last:border-0"
                >
                  <span
                    class="text-[10px] font-semibold px-[7px] py-[3px] rounded-[6px] flex-shrink-0 mt-[1px] uppercase tracking-[.03em]"
                    :style="catBadge(r.category)"
                  >{{ CAT_LABEL[r.category] ?? r.category }}</span>
                  <div class="flex-1 min-w-0">
                    <div class="text-[13px] font-semibold text-[#1a1d1d] leading-[1.4]">{{ r.title }}</div>
                    <div v-if="r.display_value" class="text-[11.5px] text-[#8a9090] mt-[2px]">{{ r.display_value }}</div>
                  </div>
                  <span
                    class="font-mono text-[12px] font-semibold flex-shrink-0 mt-[1px]"
                    :style="{ color: lhColor(r.score ?? 0) }"
                  >{{ r.score ?? 0 }}/100</span>
                </div>
              </div>
            </div>
          </section>

          <!-- Lighthouse non disponible -->
          <div v-else class="bg-white border border-[#e6e8e8] rounded-[12px] p-6 flex items-center gap-[14px]">
            <div class="w-[40px] h-[40px] rounded-[10px] bg-[#f0f1f2] flex items-center justify-center text-[18px] text-[#a4abab] flex-shrink-0">⚡</div>
            <div>
              <div class="text-[14px] font-semibold mb-1">Audit Lighthouse non disponible</div>
              <p class="m-0 text-[13px] leading-[1.55] text-[#5c6363]">
                L'audit Lighthouse n'est lancé que sur les sites à propriété confirmée. Ce site est classé <strong>{{ ownershipVerdictStyle.label.toLowerCase() }}</strong> — l'audit sera disponible après confirmation de l'ownership.
              </p>
            </div>
          </div>

        </template>
      </section>

      <!-- Contact (full width) -->
      <section class="bg-white border border-[#e6e8e8] rounded-[12px] p-[18px_20px] col-span-2">
        <h2 class="m-0 mb-[14px] text-[12px] font-semibold text-[#8a9090] uppercase tracking-[.05em]">Contact</h2>

        <!-- Contacts list -->
        <div v-if="sortedContacts.length > 0" class="flex flex-col gap-[11px]">
          <span
            v-if="conformiteMeta"
            class="inline-flex items-center gap-[6px] text-[12px] font-semibold px-[10px] py-1 rounded-[7px] self-start"
            :style="{ background: conformiteMeta.bg, color: conformiteMeta.color, border: `1px solid ${conformiteMeta.border}` }"
          >
            {{ conformiteMeta.text }}
          </span>

          <div class="flex flex-col gap-[8px]">
            <div
              v-for="contact in sortedContacts"
              :key="contact.id"
              class="flex flex-col gap-[6px] px-[13px] py-[11px] rounded-[9px]"
              :style="{
                border: contact.suspicious ? '1px solid #f6d4c2' : '1px solid #eceeef',
                background: contact.suspicious ? '#fffaf8' : '#fafbfb',
              }"
            >
              <div class="flex items-center gap-[9px] flex-wrap">
                <span
                  class="text-[10px] font-bold uppercase tracking-[.04em] px-[7px] py-[2px] rounded-[6px]"
                  :style="contact.type === 'email'
                    ? { background: '#eef2ff', color: '#4338ca', border: '1px solid #c7d2fe' }
                    : { background: '#f0fdf4', color: '#166534', border: '1px solid #bbf7d0' }"
                >
                  {{ contact.type === 'email' ? 'Email' : 'Tél.' }}
                </span>
                <span class="font-mono text-[13.5px] font-medium text-[#1a1d1d]">{{ contact.value }}</span>
                <span class="ml-auto text-[10.5px] font-medium text-[#a4abab]">{{ contact.source }}</span>
                <span
                  v-if="contact.suspicious"
                  class="text-[10px] font-semibold px-[7px] py-[2px] rounded-[6px]"
                  style="background: #fdeee6; color: #b8410e; border: 1px solid #f6d4c2;"
                >
                  À vérifier
                </span>
              </div>
              <div v-if="contact.warnings?.length" class="flex flex-col gap-[3px]">
                <p
                  v-for="(w, i) in contact.warnings"
                  :key="i"
                  class="m-0 text-[11.5px] leading-[1.45]"
                  style="color: #9a6b00;"
                >
                  ⚠ {{ w }}
                </p>
              </div>
            </div>
          </div>
        </div>

        <!-- No contacts -->
        <div v-else class="text-center py-[6px]">
          <p class="m-0 mb-[13px] text-[12.5px] text-[#8a9090] leading-[1.5]">
            {{ an ? "Aucun moyen de contact trouvé lors de l'analyse." : "Lancez l'analyse du site pour extraire les contacts (email, téléphone)." }}
          </p>
          <button
            v-if="!an"
            class="w-full bg-white border border-[#e0e3e3] text-[#3a4040] rounded-[8px] py-[10px] text-[13px] font-semibold"
            :class="{ 'opacity-60 pointer-events-none': state.analyzing }"
            @click="analyzeOne(company!.siren)"
          >
            {{ state.analyzing ? 'Analyse en cours…' : 'Analyser pour extraire les contacts' }}
          </button>
        </div>
      </section>

    </div>
  </main>
</template>
