<script setup lang="ts">
withDefaults(
  defineProps<{
    loading?: boolean
    isEmpty?: boolean
  }>(),
  {
    loading: false,
    isEmpty: false
  }
)
</script>

<template>
  <div class="section-card">
    <div v-if="loading" class="flex items-center justify-center gap-3 py-16 text-zinc-500">
      <div class="h-4 w-4 animate-spin rounded-full border-2 border-zinc-700 border-t-indigo-500"></div>
      <span class="text-sm">Loading...</span>
    </div>
    <div v-else-if="isEmpty" class="px-6 py-16 text-center">
      <slot name="empty" />
    </div>
    <div v-else class="overflow-x-auto">
      <table class="min-w-full">
        <thead>
          <tr class="border-b border-zinc-800">
            <slot name="head" />
          </tr>
        </thead>
        <tbody class="divide-y divide-zinc-800/60">
          <slot />
        </tbody>
      </table>
    </div>
    <slot v-if="!loading && !isEmpty" name="footer" />
  </div>
</template>
