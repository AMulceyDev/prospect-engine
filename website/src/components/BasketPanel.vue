<script setup lang="ts">
import { computed } from 'vue'
import { useStore } from '../composables/useStore'
import { webMeta, webStatusOf } from '../utils'

const { state, toggleBasket, clearBasket, runAnalyze, deleteSelected } = useStore()

const basketCompanies = computed(() =>
  state.basket.map(siren => state.companies.find(c => c.siren === siren)!).filter(Boolean)
)
</script>

<template>
  <aside class="w-[296px] flex-shrink-0 sticky top-[78px] bg-white border border-[#e6e8e8] rounded-[12px] overflow-hidden">
    <!-- Header -->
    <div class="px-4 py-[14px] border-b border-[#eceeef] flex items-center justify-between">
      <div class="flex items-center gap-2">
        <span class="text-[13.5px] font-semibold">Panier d'analyse</span>
        <span class="text-[11.5px] font-semibold text-[#0b7a6e] bg-[#e9f6f0] border border-[#cfe9e1] px-[7px] py-[1px] rounded-full">
          {{ state.basket.length }}
        </span>
      </div>
      <button
        v-if="state.basket.length > 0"
        class="text-[11.5px] font-medium text-[#a4abab] bg-transparent border-none p-[2px]"
        @click="clearBasket()"
      >
        Vider
      </button>
    </div>

    <!-- Basket items -->
    <template v-if="state.basket.length > 0">
      <div class="max-h-[340px] overflow-y-auto">
        <div
          v-for="c in basketCompanies"
          :key="c.siren"
          class="flex items-center gap-[10px] px-4 py-[10px] border-b border-[#f4f5f5]"
        >
          <div class="min-w-0 flex-1">
            <div class="text-[12.5px] font-semibold whitespace-nowrap overflow-hidden text-ellipsis">{{ c.denomination ?? c.siren }}</div>
            <div class="text-[11px] text-[#a4abab]">{{ c.commune ?? '—' }} · {{ webMeta(webStatusOf(c)).text }}</div>
          </div>
          <button
            class="bg-transparent border-none text-[#c4caca] text-[16px] leading-none px-[4px] py-[2px]"
            @click="toggleBasket(c.siren)"
          >×</button>
        </div>
      </div>

      <!-- Actions -->
      <div class="px-4 py-[14px] border-t border-[#eceeef]">
        <!-- Analyzing -->
        <div v-if="state.analyzing" class="flex items-center gap-[10px] justify-center py-2">
          <div class="w-4 h-4 rounded-full border-2 border-[#cfe9e1] border-t-[#0e9384] animate-pe-spin"></div>
          <span class="text-[12.5px] text-[#0b7a6e] font-medium">Analyse en cours…</span>
        </div>

        <!-- Ready -->
        <template v-else>
          <button
            class="w-full bg-[#0e9384] text-white border-none rounded-[8px] py-[10px] text-[13px] font-semibold"
            @click="runAnalyze()"
          >
            Lancer l'analyse ({{ state.basket.length }})
          </button>
          <button
            class="w-full mt-2 bg-white border border-[#f6d4c2] text-[#b8410e] rounded-[8px] py-[8px] text-[12.5px] font-semibold"
            @click="deleteSelected()"
          >
            Supprimer la sélection
          </button>
        </template>
      </div>
    </template>

    <!-- Empty state -->
    <template v-else>
      <div class="px-5 py-[30px] text-center">
        <div class="w-[38px] h-[38px] rounded-[9px] bg-[#f0f1f2] border border-dashed border-[#d4d8d8] mx-auto mb-3"></div>
        <p class="text-[12.5px] text-[#8a9090] leading-[1.5]">
          Cochez des entreprises<br>pour les ajouter au lot d'analyse.
        </p>
      </div>
    </template>
  </aside>
</template>
