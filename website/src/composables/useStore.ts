import { reactive } from 'vue'
import type { CompanyDetail, CompanyRead, SignalStyle } from '../types/index'
import { api, ApiError } from '../api'

interface Progress {
  task: string
  current: number
  total: number
}

interface StoreState {
  view: 'list' | 'detail'
  selectedSiren: string | null
  detail: CompanyDetail | null
  detailLoading: boolean
  companies: CompanyRead[]
  loading: boolean
  error: string | null
  basket: string[]
  signalStyle: SignalStyle
  fw: string[]
  fcp: string[]
  ff: string[]
  fa: string[]
  fetching: boolean
  fetchStep: string
  progress: Progress | null
  enrichingId: string | null
  enrichedIds: string[]
  analyzing: boolean
  toast: string | null
}

const state = reactive<StoreState>({
  view: 'list',
  selectedSiren: null,
  detail: null,
  detailLoading: false,
  companies: [],
  loading: false,
  error: null,
  basket: [],
  signalStyle: 'mix',
  fw: [],
  fcp: [],
  ff: [],
  fa: [],
  fetching: false,
  fetchStep: '',
  progress: null,
  enrichingId: null,
  enrichedIds: [],
  analyzing: false,
  toast: null,
})

let toastTimer: ReturnType<typeof setTimeout> | null = null

function showToast(msg: string) {
  state.toast = msg
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { state.toast = null }, 2600)
}

async function withProgress<T>(promise: Promise<T>): Promise<T> {
  const tick = setInterval(async () => {
    try {
      const p = await api.progress()
      if (p.total > 0) state.progress = p
    } catch { /* ignore */ }
  }, 600)
  try {
    return await promise
  } finally {
    clearInterval(tick)
    state.progress = null
  }
}

async function loadCompanies() {
  state.loading = true
  state.error = null
  try {
    state.companies = await api.companies.list()
  } catch (e) {
    state.error = e instanceof ApiError ? `Erreur API (${e.status})` : 'Erreur réseau'
  } finally {
    state.loading = false
  }
}

export function useStore() {
  return {
    state,
    loadCompanies,

    async goDetail(siren: string) {
      state.view = 'detail'
      state.selectedSiren = siren
      state.detail = null
      state.detailLoading = true
      try {
        state.detail = await api.companies.get(siren)
      } catch {
        state.detail = null
      } finally {
        state.detailLoading = false
      }
    },

    goList() {
      state.view = 'list'
      state.selectedSiren = null
    },

    toggleBasket(siren: string) {
      const i = state.basket.indexOf(siren)
      if (i >= 0) state.basket.splice(i, 1)
      else state.basket.push(siren)
    },

    clearBasket() {
      state.basket.splice(0)
    },

    toggleAll(sirens: string[]) {
      const allIn = sirens.every(s => state.basket.includes(s))
      if (allIn) {
        sirens.forEach(s => {
          const i = state.basket.indexOf(s)
          if (i >= 0) state.basket.splice(i, 1)
        })
      } else {
        sirens.forEach(s => {
          if (!state.basket.includes(s)) state.basket.push(s)
        })
      }
    },

    async runFetch(params: { days?: number; rows?: number } = {}) {
      state.fetching = true
      try {
        state.fetchStep = 'Recherche INSEE…'
        const ingest = await api.ingest.run({ days: params.days ?? 120, rows: params.rows ?? 50, exclude_ei: true })
        state.fetchStep = 'Filtrage des prospects…'
        const filter = await api.ingest.filter()
        state.fetchStep = 'Détection des sites web…'
        const detect = await withProgress(api.ingest.websites())
        await loadCompanies()
        showToast(
          `${ingest.processed} entreprises · ${filter.deleted} filtrées · ${detect.candidates_probed} sites vérifiés`
        )
      } catch (e) {
        showToast(e instanceof Error ? e.message : 'Erreur lors de la recherche')
      } finally {
        state.fetching = false
        state.fetchStep = ''
      }
    },

    async importRNE() {
      state.fetching = true
      try {
        state.fetchStep = 'Enrichissement RNE…'
        const enrich = await api.ingest.enrich({ limit: 200 })
        state.fetchStep = 'Détection des sites web…'
        const detect = await withProgress(api.ingest.websites())
        await loadCompanies()
        showToast(`${enrich.enriched} fiches enrichies · ${detect.candidates_probed} sites vérifiés`)
      } catch (e) {
        showToast(e instanceof Error ? e.message : "Erreur lors de l'import RNE")
      } finally {
        state.fetching = false
        state.fetchStep = ''
      }
    },

    async enrichRNE(siren: string) {
      state.enrichingId = siren
      try {
        await api.enrich(siren)
        if (state.selectedSiren === siren) {
          state.detail = await api.companies.get(siren)
        }
        await loadCompanies()
        if (!state.enrichedIds.includes(siren)) state.enrichedIds.push(siren)
        showToast('Fiche enrichie via le RNE')
      } catch (e) {
        showToast(e instanceof Error ? e.message : 'Erreur RNE')
      } finally {
        state.enrichingId = null
      }
    },

    async runAnalyze() {
      if (!state.basket.length) return
      state.analyzing = true
      const sirens = [...state.basket]
      try {
        const result = await withProgress(api.analyze.run({ limit: sirens.length, sirens }))
        await loadCompanies()
        showToast(`${result.done} site(s) analysé(s)`)
      } catch (e) {
        showToast(e instanceof Error ? e.message : "Erreur d'analyse")
      } finally {
        state.analyzing = false
      }
    },

    async deleteSelected() {
      if (!state.basket.length) return
      const sirens = [...state.basket]
      try {
        const result = await api.companies.deleteMany(sirens)
        state.basket.splice(0)
        await loadCompanies()
        showToast(`${result.deleted} entreprise(s) supprimée(s)`)
      } catch (e) {
        showToast(e instanceof Error ? e.message : 'Erreur lors de la suppression')
      }
    },

    async analyzeOne(siren: string) {
      state.analyzing = true
      try {
        const result = await withProgress(api.analyze.run({ limit: 1, sirens: [siren] }))
        if (state.selectedSiren === siren) {
          state.detail = await api.companies.get(siren)
        }
        await loadCompanies()
        showToast(result.done ? 'Analyse terminée' : 'Site non confirmé ou inaccessible')
      } catch (e) {
        showToast(e instanceof Error ? e.message : "Erreur d'analyse")
      } finally {
        state.analyzing = false
      }
    },
  }
}
