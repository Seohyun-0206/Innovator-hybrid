<script setup lang="ts">
import { ChevronLeftIcon, ChevronRightIcon } from 'lucide-vue-next'

withDefaults(
  defineProps<{
    page: number
    pageSize: number
    pageSizeOptions?: number[]
    totalItems: number
    totalPages: number
    startItem: number
    endItem: number
  }>(),
  {
    pageSizeOptions: () => [5, 10, 25, 50]
  }
)

defineEmits<{
  'update:page': [page: number]
  'update:pageSize': [pageSize: number]
}>()
</script>

<template>
  <div class="flex flex-wrap items-center justify-between gap-3 border-t border-zinc-800 px-5 py-3">
    <div class="text-sm text-zinc-500">
      <span class="font-medium text-zinc-300">{{ startItem }}</span>
      -
      <span class="font-medium text-zinc-300">{{ endItem }}</span>
      of
      <span class="font-medium text-zinc-300">{{ totalItems }}</span>
    </div>

    <div class="flex items-center gap-3">
      <label class="flex items-center gap-2 text-sm text-zinc-500">
        Rows
        <select
          :value="pageSize"
          class="rounded-md ui-input px-2 py-1.5"
          @change="$emit('update:pageSize', Number(($event.target as HTMLSelectElement).value))"
        >
          <option v-for="option in pageSizeOptions" :key="option" :value="option">{{ option }}</option>
        </select>
      </label>

      <div class="flex items-center gap-1">
        <button
          class="rounded-md border border-zinc-700 bg-zinc-800 p-1.5 text-zinc-400 transition hover:bg-zinc-700 hover:text-zinc-100 disabled:cursor-not-allowed disabled:opacity-40"
          :disabled="page <= 1"
          title="Previous page"
          type="button"
          @click="$emit('update:page', page - 1)"
        >
          <ChevronLeftIcon class="h-4 w-4" />
        </button>
        <span class="min-w-20 text-center text-sm text-zinc-400">
          {{ page }} / {{ totalPages }}
        </span>
        <button
          class="rounded-md border border-zinc-700 bg-zinc-800 p-1.5 text-zinc-400 transition hover:bg-zinc-700 hover:text-zinc-100 disabled:cursor-not-allowed disabled:opacity-40"
          :disabled="page >= totalPages"
          title="Next page"
          type="button"
          @click="$emit('update:page', page + 1)"
        >
          <ChevronRightIcon class="h-4 w-4" />
        </button>
      </div>
    </div>
  </div>
</template>
