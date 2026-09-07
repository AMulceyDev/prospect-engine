<script setup lang="ts">
import { computed } from 'vue'
import type { CompanyRead } from '../types/index'
import { oppOf, oppKeyOf, oppColors, gradeOf, gradeColors, siteScoreOf, verdictTextOf } from '../utils'

const props = defineProps<{
  company: CompanyRead
  signalStyle: string
}>()

const opp = computed(() => oppOf(props.company))
const oc = computed(() => oppColors(oppKeyOf(opp.value)))
const siteScore = computed(() => siteScoreOf(props.company))
const grade = computed(() => gradeOf(siteScore.value))
const gc = computed(() => gradeColors(grade.value))
const verdictText = computed(() => verdictTextOf(props.company))
const analyzed = computed(() => props.company.analysis !== null)
</script>

<template>
  <div class="min-w-0">
    <!-- Not analyzed -->
    <template v-if="!analyzed">
      <span class="inline-flex items-center gap-[6px] text-[11.5px] font-medium text-[#a4abab] bg-[#f6f7f7] border border-dashed border-[#e0e3e3] px-[9px] py-[3px] rounded-full">
        Non analysé
      </span>
    </template>

    <!-- Badge mode -->
    <template v-else-if="signalStyle === 'badge'">
      <span
        class="inline-flex items-center gap-[6px] px-[9px] py-[3px] rounded-full text-[11.5px] font-semibold"
        :style="{ background: oc.bg, color: oc.text, border: `1px solid ${oc.border}` }"
      >
        <span class="w-[6px] h-[6px] rounded-full flex-shrink-0" :style="{ background: oc.dot }"></span>
        {{ verdictText }}
      </span>
    </template>

    <!-- Score mode -->
    <template v-else-if="signalStyle === 'score'">
      <div class="flex items-center gap-[9px]">
        <div class="flex-1 h-[7px] rounded-full bg-[#eceeef] overflow-hidden max-w-[120px]">
          <div class="h-full rounded-full" :style="{ width: opp + '%', background: oc.dot }"></div>
        </div>
        <span class="font-mono text-[12.5px] font-medium min-w-[26px]" :style="{ color: oc.text }">{{ opp }}</span>
      </div>
    </template>

    <!-- Grade mode -->
    <template v-else-if="signalStyle === 'grade'">
      <div class="flex items-center gap-[8px]">
        <span
          class="inline-flex items-center justify-center min-w-[26px] h-[24px] px-[7px] rounded-[7px] font-mono text-[13px] font-semibold"
          :style="{ background: gc.bg, color: gc.text, border: `1px solid ${gc.border}` }"
        >{{ grade }}</span>
        <span class="text-[11px] text-[#a4abab]">{{ grade === '—' ? 'aucun site' : 'qualité site' }}</span>
      </div>
    </template>

    <!-- Mix mode (default) -->
    <template v-else>
      <div class="flex flex-col gap-[5px]">
        <span
          class="inline-flex items-center gap-[6px] px-[9px] py-[3px] rounded-full text-[11.5px] font-semibold"
          :style="{ background: oc.bg, color: oc.text, border: `1px solid ${oc.border}` }"
        >
          <span class="w-[6px] h-[6px] rounded-full flex-shrink-0" :style="{ background: oc.dot }"></span>
          {{ verdictText }}
        </span>
        <div class="h-[5px] rounded-full bg-[#eceeef] overflow-hidden max-w-[130px]">
          <div class="h-full rounded-full" :style="{ width: opp + '%', background: oc.dot }"></div>
        </div>
      </div>
    </template>
  </div>
</template>
