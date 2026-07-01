<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { DownloadIcon, RefreshCwIcon, XIcon } from 'lucide-vue-next'
import { ProviderCredential, ProviderModelCandidate } from '../../composables/useApi'

const props = defineProps<{
  credential: ProviderCredential
  models: ProviderModelCandidate[]
  loading: boolean
  importing: boolean
}>()

const emit = defineEmits<{
  close: []
  refresh: []
  import: [modelNames: string[]]
}>()

const selected = ref<string[]>([])
const importableModels = computed(() => props.models.filter((model) => !model.exists))

function toggleAll() {
  if (selected.value.length === importableModels.value.length) {
    selected.value = []
    return
  }
  selected.value = importableModels.value.map((model) => model.name)
}

watch(
  importableModels,
  (models) => {
    selected.value = models.map((model) => model.name)
  },
  { immediate: true }
)
</script>

<template>
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm" @click="emit('close')">
    <div class="max-h-[90vh] w-full max-w-4xl overflow-y-auto rounded-xl border border-zinc-800 bg-zinc-900 shadow-2xl animate-fade-in" @click.stop>
      <header class="flex items-center justify-between border-b border-zinc-800 px-6 py-5">
        <div>
          <p class="mb-1 text-xs font-semibold uppercase tracking-widest text-indigo-400">모델 동기화</p>
          <h3 class="text-lg font-semibold text-zinc-100">{{ credential.display_name }}</h3>
          <p class="mt-1 text-xs text-zinc-500">{{ credential.provider }} · {{ credential.base_url }}</p>
        </div>
        <button class="rounded-lg p-1.5 text-zinc-500 transition-colors hover:bg-zinc-800 hover:text-zinc-200" type="button" @click="emit('close')">
          <XIcon class="h-5 w-5" />
        </button>
      </header>

      <div class="p-6">
        <div class="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div class="text-sm text-zinc-400">
            신규 {{ importableModels.length }}개 / 조회 {{ models.length }}개
          </div>
          <div class="flex items-center gap-2">
            <button
              class="inline-flex items-center gap-2 rounded-lg border border-zinc-700 px-3 py-2 text-sm font-medium text-zinc-300 transition-colors hover:bg-zinc-800"
              type="button"
              :disabled="loading"
              @click="emit('refresh')"
            >
              <RefreshCwIcon :class="['h-4 w-4', loading ? 'animate-spin' : '']" />
              새로고침
            </button>
            <button
              class="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white transition-colors hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-50"
              type="button"
              :disabled="!selected.length || importing"
              @click="emit('import', selected)"
            >
              <DownloadIcon class="h-4 w-4" />
              선택 모델 가져오기
            </button>
          </div>
        </div>

        <div v-if="loading" class="flex items-center justify-center gap-3 py-16 text-zinc-500">
          <div class="h-4 w-4 animate-spin rounded-full border-2 border-zinc-700 border-t-indigo-500"></div>
          <span class="text-sm">Provider 모델 목록을 조회하는 중...</span>
        </div>

        <div v-else class="overflow-hidden rounded-xl border border-zinc-800">
          <table class="min-w-full">
            <thead>
              <tr class="border-b border-zinc-800">
                <th class="w-12 px-5 py-3.5 text-left">
                  <input
                    class="h-4 w-4 rounded border-zinc-600 bg-zinc-800 accent-indigo-500"
                    type="checkbox"
                    :checked="selected.length === importableModels.length && importableModels.length > 0"
                    :disabled="!importableModels.length"
                    @change="toggleAll"
                  />
                </th>
                <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">모델</th>
                <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">컨텍스트</th>
                <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">상태</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-zinc-800/60">
              <tr v-for="model in models" :key="model.name" class="table-row">
                <td class="px-5 py-3.5">
                  <input
                    v-model="selected"
                    class="h-4 w-4 rounded border-zinc-600 bg-zinc-800 accent-indigo-500"
                    type="checkbox"
                    :value="model.name"
                    :disabled="model.exists"
                  />
                </td>
                <td class="px-5 py-3.5">
                  <div class="font-medium text-zinc-200">{{ model.display_name }}</div>
                  <div class="text-xs text-zinc-500">{{ model.name }}</div>
                </td>
                <td class="whitespace-nowrap px-5 py-3.5 text-sm text-zinc-400">{{ model.context_window }}</td>
                <td class="whitespace-nowrap px-5 py-3.5">
                  <span
                    :class="[
                      'rounded-md border px-2 py-0.5 text-xs font-medium',
                      model.exists
                        ? 'border-zinc-700 bg-zinc-800 text-zinc-500'
                        : 'border-emerald-500/20 bg-emerald-500/10 text-emerald-300'
                    ]"
                  >
                    {{ model.exists ? '등록됨' : '신규' }}
                  </span>
                </td>
              </tr>
              <tr v-if="!models.length">
                <td colspan="4" class="px-5 py-12 text-center text-sm text-zinc-600">조회된 Provider 모델이 없습니다</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>
