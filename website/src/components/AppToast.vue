<script setup lang="ts">
import { useStore } from '../composables/useStore'

const { state } = useStore()
</script>

<template>
  <Transition name="toast">
    <div
      v-if="state.toast"
      class="fixed bottom-6 left-1/2 -translate-x-1/2 z-[60] bg-[#1a1d1d] text-white px-[18px] py-[11px] rounded-[10px] text-[13px] font-medium shadow-[0_8px_24px_rgba(0,0,0,.2)] flex items-center gap-[9px]"
    >
      <span class="w-[7px] h-[7px] rounded-full bg-[#3dd7b8]"></span>
      {{ state.toast }}
    </div>
  </Transition>
</template>

<style scoped>
.toast-enter-active { animation: pe-fade .25s ease; }
.toast-leave-active { transition: opacity .2s ease; }
.toast-leave-to { opacity: 0; }

@keyframes pe-fade {
  from { opacity: 0; transform: translate(-50%, 4px); }
  to   { opacity: 1; transform: translate(-50%, 0); }
}
</style>
