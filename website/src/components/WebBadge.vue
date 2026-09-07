<script setup lang="ts">
import { computed } from 'vue'
import type { WebStatus } from '../types/index'
import { webMeta } from '../utils'

const props = defineProps<{
  web: WebStatus
  domain?: string | null
  confidence?: number
}>()

const meta = computed(() => webMeta(props.web))
const uncertain = computed(() => props.web !== 'none' && (props.confidence ?? 0) > 0 && (props.confidence ?? 0) < 60)
</script>

<template>
  <div>
    <span
      class="inline-flex items-center gap-[6px] px-[9px] py-[3px] rounded-full text-[11.5px] font-semibold"
      :style="{
        color: meta.color,
        background: meta.bg,
        border: `1px ${meta.dashed ? 'dashed' : 'solid'} ${meta.border}`,
      }"
    >
      <span class="w-[6px] h-[6px] rounded-full flex-shrink-0" :style="{ background: meta.dot }"></span>
      {{ meta.text }}
    </span>

    <div v-if="domain" class="flex items-center gap-[6px] mt-1">
      <span class="font-mono text-[11px] text-[#5c6363] whitespace-nowrap overflow-hidden text-ellipsis">{{ domain }}</span>
      <span
        v-if="confidence"
        class="text-[10.5px] font-medium whitespace-nowrap"
        :style="uncertain
          ? { color: '#9a6b00', background: '#fdf6e3', padding: '1px 6px', borderRadius: '5px' }
          : { color: '#a4abab' }"
      >
        {{ confidence }}%{{ uncertain ? ' · incertain' : '' }}
      </span>
    </div>
  </div>
</template>
