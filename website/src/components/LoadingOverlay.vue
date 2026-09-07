<script setup lang="ts">
import { computed } from 'vue'
import { useStore } from '../composables/useStore'

const { state } = useStore()

const stepLabel = computed(() => {
  if (state.analyzing) return 'Analyse en cours…'
  return state.fetchStep || 'Traitement en cours…'
})

const progressLabel = computed(() => {
  const p = state.progress
  if (!p || p.total === 0) return null
  const what = p.task === 'analyze' ? 'entreprise' : 'site'
  const plural = p.current > 1 ? 's' : ''
  return { text: `${p.current} / ${p.total} ${what}${plural}`, pct: p.current / p.total }
})
</script>

<template>
  <Transition name="fade">
    <div
      v-if="state.fetching || state.analyzing"
      class="fixed inset-0 z-50 flex items-center justify-center"
      style="background: rgba(245,246,247,.78); backdrop-filter: blur(2px);"
    >
      <div class="bg-white border border-[#e6e8e8] rounded-[14px] px-[34px] py-[26px] flex flex-col items-center gap-[14px] shadow-[0_8px_30px_rgba(0,0,0,.08)] w-[300px]">
        <div class="w-[30px] h-[30px] rounded-full border-[3px] border-[#cfe9e1] border-t-[#0e9384] animate-pe-spin"></div>

        <div class="w-full text-center">
          <div class="text-[14px] font-semibold">{{ stepLabel }}</div>

          <!-- Progress bar (only when we have data) -->
          <template v-if="progressLabel">
            <div class="mt-[10px] h-[6px] rounded-full bg-[#eceeef] overflow-hidden">
              <div
                class="h-full rounded-full bg-[#0e9384] transition-all duration-500"
                :style="{ width: (progressLabel.pct * 100) + '%' }"
              ></div>
            </div>
            <div class="mt-[6px] font-mono text-[12px] text-[#8a9090]">{{ progressLabel.text }}</div>
          </template>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity .2s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
