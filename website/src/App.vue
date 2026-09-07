<script setup lang="ts">
import { computed } from 'vue'
import { useStore } from './composables/useStore'
import AppHeader from './components/AppHeader.vue'
import LoadingOverlay from './components/LoadingOverlay.vue'
import AppToast from './components/AppToast.vue'
import ListView from './views/ListView.vue'
import DetailView from './views/DetailView.vue'

const { state } = useStore()

const showDetail = computed(() => state.view === 'detail' && !!state.selectedSiren)
</script>

<template>
  <div class="min-h-screen bg-[#f5f6f7] font-sans text-[#1a1d1d]">
    <AppHeader />
    <ListView v-if="!showDetail" />
    <DetailView v-else />
    <LoadingOverlay />
    <AppToast />
  </div>
</template>
