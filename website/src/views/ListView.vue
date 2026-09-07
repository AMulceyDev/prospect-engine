<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useStore } from '../composables/useStore'
import WebBadge from '../components/WebBadge.vue'
import SignalCell from '../components/SignalCell.vue'
import BasketPanel from '../components/BasketPanel.vue'
import { webStatusOf, formeAbbr } from '../utils'
import type { WebStatus } from '../types/index'

const { state, loadCompanies, goDetail, toggleBasket, toggleAll, runFetch } = useStore()

onMounted(loadCompanies)

const dateFrom = ref(new Date(Date.now() - 120 * 86400_000).toISOString().slice(0, 10))
const rows = ref(50)
const searchQuery = ref('')
const sortApe = ref(false)
const openFilter = ref<string | null>(null)

const daysBack = computed(() => {
  const from = new Date(dateFrom.value).getTime()
  return Math.max(1, Math.round((Date.now() - from) / 86400_000))
})

// Dynamic checklist options — only values present in loaded data
const apeOptions = computed(() => {
  const map = new Map<string, string>()
  for (const c of state.companies) {
    if (c.code_ape && !map.has(c.code_ape)) {
      const label = c.code_ape_label || c.code_ape
      map.set(c.code_ape, `${c.code_ape} – ${label}`)
    }
  }
  return [...map.entries()]
    .map(([value, label]) => ({ value, label }))
    .sort((a, b) => a.value.localeCompare(b.value))
})

const cpOptions = computed(() =>
  ([...new Set(state.companies.map(c => c.code_postal).filter((v): v is string => !!v))]).sort()
)

const formeOptions = computed(() =>
  ([...new Set(state.companies.map(c => formeAbbr(c.forme_juridique)).filter(v => v !== '—'))]).sort()
)

const webOptions = computed(() => {
  const present = new Set(state.companies.map(c => webStatusOf(c)))
  return [
    { value: 'site',    label: 'Site détecté' },
    { value: 'none',    label: 'Pas de site' },
    { value: 'unknown', label: 'À vérifier' },
  ].filter(o => present.has(o.value as WebStatus))
})

// Filtering: union within a filter group, intersection across groups
const filtered = computed(() => {
  let list = state.companies

  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase()
    list = list.filter(c =>
      c.siren.includes(q) ||
      (c.denomination ?? '').toLowerCase().includes(q) ||
      (c.commune ?? '').toLowerCase().includes(q)
    )
  }

  if (state.fa.length)  list = list.filter(c => c.code_ape != null && state.fa.includes(c.code_ape))
  if (state.fw.length)  list = list.filter(c => state.fw.includes(webStatusOf(c)))
  if (state.fcp.length) list = list.filter(c => c.code_postal != null && state.fcp.includes(c.code_postal))
  if (state.ff.length)  list = list.filter(c => state.ff.includes(formeAbbr(c.forme_juridique)))

  if (sortApe.value) {
    list = [...list].sort((a, b) => {
      const la = a.code_ape_label || a.code_ape || ''
      const lb = b.code_ape_label || b.code_ape || ''
      if (!la) return 1
      if (!lb) return -1
      return la.localeCompare(lb, 'fr')
    })
  }

  return list
})

const allChecked = computed(() =>
  filtered.value.length > 0 && filtered.value.every(c => state.basket.includes(c.siren))
)

// Purge filter selections that no longer match any company in the refreshed dataset
watch(() => state.companies, (companies) => {
  const validApe = new Set(companies.map(c => c.code_ape).filter((v): v is string => !!v))
  const validCp  = new Set(companies.map(c => c.code_postal).filter((v): v is string => !!v))
  const validFf  = new Set(companies.map(c => formeAbbr(c.forme_juridique)).filter(v => v !== '—'))
  const validFw  = new Set<string>(companies.map(c => webStatusOf(c)))

  state.fa  = state.fa.filter(v => validApe.has(v))
  state.fcp = state.fcp.filter(v => validCp.has(v))
  state.ff  = state.ff.filter(v => validFf.has(v))
  state.fw  = state.fw.filter(v => validFw.has(v))
})

function toggleFilter(name: string) {
  openFilter.value = openFilter.value === name ? null : name
}

function resetFilters() {
  state.fa.splice(0)
  state.fw.splice(0)
  state.fcp.splice(0)
  state.ff.splice(0)
  searchQuery.value = ''
  openFilter.value = null
}
</script>

<template>
  <main class="max-w-[1320px] mx-auto px-7 pt-[26px] pb-20">

    <!-- Backdrop: closes open filter dropdown when clicking outside -->
    <div v-if="openFilter" class="fixed inset-0 z-10" @click="openFilter = null"></div>

    <!-- Toolbar -->
    <div class="flex items-end justify-between gap-6 flex-wrap mb-[18px]">
      <div>
        <!-- Title -->
        <div class="flex items-center gap-[11px]">
          <h1 class="m-0 text-[21px] font-semibold tracking-[-0.02em]">Prospects</h1>
          <span class="text-[12.5px] font-semibold text-[#0b7a6e] bg-[#e9f6f0] border border-[#cfe9e1] px-[9px] py-[3px] rounded-full">
            {{ filtered.length }} entreprises
          </span>
          <div v-if="state.loading" class="w-4 h-4 rounded-full border-2 border-[#cfe9e1] border-t-[#0e9384] animate-pe-spin"></div>
        </div>
        <p class="mt-[5px] mb-0 text-[13px] text-[#8a9090]">
          Entreprises issues de la dernière recherche
        </p>
        <p v-if="state.error" class="mt-[5px] mb-0 text-[12.5px] text-[#b8410e]">{{ state.error }}</p>
      </div>

      <!-- Fetch control -->
      <div class="flex items-end gap-[10px] bg-white border border-[#e6e8e8] rounded-[11px] px-[13px] py-[11px]">
        <div class="flex flex-col gap-1">
          <label class="text-[10.5px] font-semibold text-[#8a9090] uppercase tracking-[.04em]">Crée le</label>
          <input v-model="dateFrom" type="date" class="border border-[#e0e3e3] rounded-[7px] px-2 py-[6px] text-[12.5px] text-[#1a1d1d] bg-white">
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-[10.5px] font-semibold text-[#8a9090] uppercase tracking-[.04em]">Nb max</label>
          <input v-model.number="rows" type="number" min="10" max="200" step="10" class="border border-[#e0e3e3] rounded-[7px] px-2 py-[6px] text-[12.5px] text-[#1a1d1d] bg-white w-[72px]">
        </div>
        <button
          class="bg-[#0e9384] text-white border-none rounded-[7px] px-[14px] h-[33px] text-[12.5px] font-semibold"
          @click="runFetch({ days: daysBack, rows })"
        >
          Lancer la recherche
        </button>
      </div>
    </div>

    <!-- Filter bar -->
    <div class="flex items-center gap-3 flex-wrap mb-[14px] px-[14px] py-3 bg-white border border-[#e6e8e8] rounded-[11px]">
      <span class="text-[11px] font-semibold text-[#8a9090] uppercase tracking-[.05em] flex-shrink-0">Filtres</span>

      <!-- Activité (APE) checklist -->
      <div class="relative flex-shrink-0">
        <button
          class="flex items-center gap-[5px] rounded-[7px] pl-[9px] pr-[8px] py-[6px] text-[12.5px] font-medium border transition-colors"
          :class="state.fa.length ? 'bg-[#e9f6f0] border-[#cfe9e1] text-[#0b7a6e]' : 'bg-white border-[#e0e3e3] text-[#3a4040]'"
          @click.stop="toggleFilter('ape')"
        >
          <span>Activité</span>
          <span v-if="state.fa.length" class="text-[11px]">({{ state.fa.length }})</span>
          <span class="text-[10px] text-[#c4caca] ml-[1px]">▾</span>
        </button>
        <div
          v-if="openFilter === 'ape'"
          class="absolute top-full left-0 mt-1 z-20 bg-white border border-[#e6e8e8] rounded-[10px] shadow-lg p-[10px] min-w-[260px] max-h-[240px] overflow-y-auto flex flex-col gap-[7px] animate-pe-fade"
          @click.stop
        >
          <label
            v-for="opt in apeOptions"
            :key="opt.value"
            class="flex items-start gap-[8px] text-[12px] text-[#1a1d1d] cursor-pointer select-none"
          >
            <input type="checkbox" :value="opt.value" v-model="state.fa" class="w-[14px] h-[14px] accent-[#0e9384] cursor-pointer mt-[1px] flex-shrink-0">
            <span>{{ opt.label }}</span>
          </label>
          <p v-if="apeOptions.length === 0" class="m-0 text-[12px] text-[#a4abab]">Aucune valeur</p>
        </div>
      </div>

      <!-- Forme juridique checklist -->
      <div class="relative flex-shrink-0">
        <button
          class="flex items-center gap-[5px] rounded-[7px] pl-[9px] pr-[8px] py-[6px] text-[12.5px] font-medium border transition-colors"
          :class="state.ff.length ? 'bg-[#e9f6f0] border-[#cfe9e1] text-[#0b7a6e]' : 'bg-white border-[#e0e3e3] text-[#3a4040]'"
          @click.stop="toggleFilter('ff')"
        >
          <span>Forme</span>
          <span v-if="state.ff.length" class="text-[11px]">({{ state.ff.length }})</span>
          <span class="text-[10px] text-[#c4caca] ml-[1px]">▾</span>
        </button>
        <div
          v-if="openFilter === 'ff'"
          class="absolute top-full left-0 mt-1 z-20 bg-white border border-[#e6e8e8] rounded-[10px] shadow-lg p-[10px] min-w-[160px] max-h-[240px] overflow-y-auto flex flex-col gap-[7px] animate-pe-fade"
          @click.stop
        >
          <label
            v-for="opt in formeOptions"
            :key="opt"
            class="flex items-center gap-[8px] text-[12px] text-[#1a1d1d] cursor-pointer select-none"
          >
            <input type="checkbox" :value="opt" v-model="state.ff" class="w-[14px] h-[14px] accent-[#0e9384] cursor-pointer flex-shrink-0">
            <span>{{ opt }}</span>
          </label>
          <p v-if="formeOptions.length === 0" class="m-0 text-[12px] text-[#a4abab]">Aucune valeur</p>
        </div>
      </div>

      <!-- Code postal checklist -->
      <div class="relative flex-shrink-0">
        <button
          class="flex items-center gap-[5px] rounded-[7px] pl-[9px] pr-[8px] py-[6px] text-[12.5px] font-medium border transition-colors"
          :class="state.fcp.length ? 'bg-[#e9f6f0] border-[#cfe9e1] text-[#0b7a6e]' : 'bg-white border-[#e0e3e3] text-[#3a4040]'"
          @click.stop="toggleFilter('cp')"
        >
          <span>Code postal</span>
          <span v-if="state.fcp.length" class="text-[11px]">({{ state.fcp.length }})</span>
          <span class="text-[10px] text-[#c4caca] ml-[1px]">▾</span>
        </button>
        <div
          v-if="openFilter === 'cp'"
          class="absolute top-full left-0 mt-1 z-20 bg-white border border-[#e6e8e8] rounded-[10px] shadow-lg p-[10px] min-w-[140px] max-h-[240px] overflow-y-auto flex flex-col gap-[7px] animate-pe-fade"
          @click.stop
        >
          <label
            v-for="cp in cpOptions"
            :key="cp"
            class="flex items-center gap-[8px] text-[12px] font-mono text-[#1a1d1d] cursor-pointer select-none"
          >
            <input type="checkbox" :value="cp" v-model="state.fcp" class="w-[14px] h-[14px] accent-[#0e9384] cursor-pointer flex-shrink-0">
            <span>{{ cp }}</span>
          </label>
          <p v-if="cpOptions.length === 0" class="m-0 text-[12px] text-[#a4abab]">Aucune valeur</p>
        </div>
      </div>

      <!-- Présence web checklist -->
      <div class="relative flex-shrink-0">
        <button
          class="flex items-center gap-[5px] rounded-[7px] pl-[9px] pr-[8px] py-[6px] text-[12.5px] font-medium border transition-colors"
          :class="state.fw.length ? 'bg-[#e9f6f0] border-[#cfe9e1] text-[#0b7a6e]' : 'bg-white border-[#e0e3e3] text-[#3a4040]'"
          @click.stop="toggleFilter('fw')"
        >
          <span>Présence web</span>
          <span v-if="state.fw.length" class="text-[11px]">({{ state.fw.length }})</span>
          <span class="text-[10px] text-[#c4caca] ml-[1px]">▾</span>
        </button>
        <div
          v-if="openFilter === 'fw'"
          class="absolute top-full left-0 mt-1 z-20 bg-white border border-[#e6e8e8] rounded-[10px] shadow-lg p-[10px] min-w-[170px] flex flex-col gap-[7px] animate-pe-fade"
          @click.stop
        >
          <label
            v-for="opt in webOptions"
            :key="opt.value"
            class="flex items-center gap-[8px] text-[12px] text-[#1a1d1d] cursor-pointer select-none"
          >
            <input type="checkbox" :value="opt.value" v-model="state.fw" class="w-[14px] h-[14px] accent-[#0e9384] cursor-pointer flex-shrink-0">
            <span>{{ opt.label }}</span>
          </label>
          <p v-if="webOptions.length === 0" class="m-0 text-[12px] text-[#a4abab]">Aucune valeur</p>
        </div>
      </div>

      <!-- Reset -->
      <button
        class="bg-white border border-[#e0e3e3] text-[#5c6363] rounded-[7px] px-3 py-[7px] text-[12px] font-medium"
        @click="resetFilters"
      >
        Réinitialiser
      </button>

      <!-- Search bar (replaces signal style toggle) -->
      <div class="ml-auto flex items-center gap-[6px] bg-white border border-[#e0e3e3] rounded-[7px] pl-[9px] pr-[8px] py-[6px]" @click.stop>
        <svg class="w-[13px] h-[13px] text-[#a4abab] flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
          <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-4.35-4.35M11 19a8 8 0 100-16 8 8 0 000 16z"/>
        </svg>
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Rechercher…"
          class="border-none outline-none text-[12.5px] bg-transparent text-[#1a1d1d] w-[170px] placeholder:text-[#a4abab]"
        >
        <button
          v-if="searchQuery"
          class="text-[#a4abab] hover:text-[#5c6363] text-[16px] leading-none border-none bg-transparent p-0 cursor-pointer flex-shrink-0"
          @click="searchQuery = ''"
        >×</button>
      </div>
    </div>

    <!-- Main content: table + basket -->
    <div class="flex gap-[18px] items-start">
      <!-- Table -->
      <div class="flex-1 min-w-0 bg-white border border-[#e6e8e8] rounded-[12px] overflow-hidden">
        <!-- Table header -->
        <div class="prospect-grid px-4 py-[11px] bg-[#fafbfb] border-b border-[#eceeef]">
          <div class="flex items-center justify-center">
            <input
              type="checkbox"
              :checked="allChecked"
              class="w-[15px] h-[15px] accent-[#0e9384] cursor-pointer"
              @change="toggleAll(filtered.map(c => c.siren))"
            >
          </div>
          <!-- Entreprise header: click to toggle sort by APE label -->
          <span
            class="text-[11px] font-semibold uppercase tracking-[.05em] cursor-pointer select-none flex items-center gap-[4px]"
            :class="sortApe ? 'text-[#0b7a6e]' : 'text-[#8a9090] hover:text-[#3a4040]'"
            title="Trier par activité"
            @click="sortApe = !sortApe"
          >
            Entreprise
            <span class="font-mono text-[10px]" :class="sortApe ? 'text-[#0e9384]' : 'text-[#c4caca]'">{{ sortApe ? '↑' : '↕' }}</span>
          </span>
          <span class="text-[11px] font-semibold text-[#8a9090] uppercase tracking-[.05em]">Localisation</span>
          <span class="text-[11px] font-semibold text-[#8a9090] uppercase tracking-[.05em]">Forme</span>
          <span class="text-[11px] font-semibold text-[#8a9090] uppercase tracking-[.05em]">Présence web</span>
          <span class="text-[11px] font-semibold text-[#8a9090] uppercase tracking-[.05em]">Signal · opportunité</span>
          <span></span>
        </div>

        <!-- Loading skeleton -->
        <div v-if="state.loading && state.companies.length === 0" class="py-16 px-6 text-center">
          <div class="w-4 h-4 rounded-full border-2 border-[#cfe9e1] border-t-[#0e9384] animate-pe-spin mx-auto mb-3"></div>
          <p class="m-0 text-[13px] text-[#a4abab]">Chargement des entreprises…</p>
        </div>

        <!-- Empty state -->
        <div v-else-if="filtered.length === 0" class="py-16 px-6 text-center">
          <div class="w-[44px] h-[44px] rounded-[11px] bg-[#f0f1f2] mx-auto mb-[14px] flex items-center justify-center text-[20px] text-[#a4abab]">∅</div>
          <p class="m-0 text-[14px] font-semibold text-[#5c6363]">
            {{ state.companies.length === 0 ? 'Aucune entreprise dans la base' : 'Aucune entreprise ne correspond' }}
          </p>
          <p class="mt-[6px] mb-0 text-[13px] text-[#a4abab]">
            {{ state.companies.length === 0 ? 'Lancez une recherche pour importer des entreprises.' : 'Élargissez les filtres ou lancez une nouvelle recherche.' }}
          </p>
        </div>

        <!-- Rows -->
        <div
          v-for="c in filtered"
          :key="c.siren"
          class="prospect-grid px-4 py-[13px] border-b border-[#f4f5f5] cursor-pointer transition-colors duration-[120ms]"
          :style="{ background: state.basket.includes(c.siren) ? '#f1faf7' : '#fff' }"
          @click="goDetail(c.siren)"
        >
          <!-- Checkbox -->
          <div class="flex items-center justify-center" @click.stop>
            <input
              type="checkbox"
              :checked="state.basket.includes(c.siren)"
              class="w-[15px] h-[15px] accent-[#0e9384] cursor-pointer"
              @change="toggleBasket(c.siren)"
            >
          </div>

          <!-- Name + APE code -->
          <div class="min-w-0">
            <div class="text-[13.5px] font-semibold text-[#1a1d1d] whitespace-nowrap overflow-hidden text-ellipsis">{{ c.denomination ?? c.siren }}</div>
            <div class="text-[11.5px] text-[#8a9090] whitespace-nowrap overflow-hidden text-ellipsis mt-[1px] font-mono">{{ c.code_ape ?? '' }}</div>
          </div>

          <!-- Location -->
          <div>
            <div class="text-[12.5px] text-[#3a4040] font-medium">{{ c.commune ?? '—' }}</div>
            <div class="font-mono text-[11px] text-[#a4abab]">{{ c.code_postal ?? '' }}</div>
          </div>

          <!-- Legal form -->
          <div>
            <span class="inline-block text-[11.5px] font-semibold text-[#5c6363] bg-[#f0f1f2] border border-[#e6e8e8] px-2 py-[2px] rounded-[6px]">
              {{ formeAbbr(c.forme_juridique) }}
            </span>
          </div>

          <!-- Web presence: badge only, no URL in list view -->
          <div>
            <WebBadge :web="webStatusOf(c)" />
          </div>

          <!-- Signal -->
          <SignalCell :company="c" signal-style="mix" />

          <!-- Arrow -->
          <div class="text-[#c4caca] text-[16px] text-center">›</div>
        </div>
      </div>

      <!-- Basket panel -->
      <BasketPanel />
    </div>
  </main>
</template>
