<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { DatabaseIcon, EyeIcon, SearchIcon, TrashIcon, XIcon } from 'lucide-vue-next'
import AdminDataTable from '../components/common/AdminDataTable.vue'
import { GeneratedDataset, useApi } from '../composables/useApi'

const api = useApi()
const datasets = ref<GeneratedDataset[]>([])
const loading = ref(false)
const searchQuery = ref('')
const error = ref('')
const selected = ref<GeneratedDataset | null>(null)
let pollTimer: number | undefined

const filtered = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()
  return datasets.value.filter(
    (item) =>
      !query ||
      item.name.toLowerCase().includes(query) ||
      item.service_feature_name.toLowerCase().includes(query) ||
      (item.generation_model_label || '').toLowerCase().includes(query) ||
      item.dataset_type.toLowerCase().includes(query)
  )
})

const hasRunningGeneration = computed(() =>
  datasets.value.some((item) => item.status === 'pending' || item.status === 'running')
)

async function load() {
  loading.value = true
  error.value = ''
  try {
    datasets.value = await api.getGeneratedDatasets()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '생성 데이터셋을 불러오지 못했습니다.'
  } finally {
    loading.value = false
  }
}

function startPolling() {
  if (pollTimer) return
  pollTimer = window.setInterval(async () => {
    await load()
    if (!hasRunningGeneration.value && pollTimer) {
      window.clearInterval(pollTimer)
      pollTimer = undefined
    }
  }, 3000)
}

async function remove(dataset: GeneratedDataset) {
  if (!confirm(`"${dataset.name}" 생성 데이터셋을 삭제할까요?`)) return
  error.value = ''
  try {
    await api.deleteGeneratedDataset(dataset.id)
    if (selected.value?.id === dataset.id) selected.value = null
    await load()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '생성 데이터셋을 삭제하지 못했습니다.'
  }
}

function previewContent(dataset: GeneratedDataset) {
  return dataset.raw_content.split('\n').filter(Boolean).join('\n')
}

function statusClass(status: string) {
  if (status === 'completed') return 'border-emerald-500/20 bg-emerald-500/10 text-emerald-300'
  if (status === 'failed') return 'border-red-500/20 bg-red-500/10 text-red-300'
  return 'border-amber-500/20 bg-amber-500/10 text-amber-300'
}

function statusLabel(status: string) {
  if (status === 'completed') return '완료'
  if (status === 'failed') return '실패'
  if (status === 'pending') return '대기'
  return '생성중'
}

onMounted(async () => {
  await load()
  if (hasRunningGeneration.value) startPolling()
  window.addEventListener('reload-generated-datasets', load)
})

onBeforeUnmount(() => {
  if (pollTimer) window.clearInterval(pollTimer)
  window.removeEventListener('reload-generated-datasets', load)
})
</script>

<template>
  <div class="p-6 lg:p-8">
    <div class="mb-6">
      <p class="mb-1 text-xs font-semibold uppercase tracking-widest text-indigo-400">리소스</p>
      <h2 class="text-2xl font-bold text-zinc-100">생성 데이터셋</h2>
      <p class="mt-1 text-sm text-zinc-500">대상 서비스별로 LLM이 생성한 평가 데이터셋을 1:1로 관리합니다.</p>
    </div>

    <div class="mb-5 relative">
      <SearchIcon class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
      <input v-model="searchQuery" class="w-full max-w-sm rounded-lg border border-zinc-700 bg-zinc-800 py-2.5 pl-9 pr-4 text-sm text-zinc-200 placeholder-zinc-600 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50" placeholder="서비스, 모델, 데이터셋 검색..." type="text" />
    </div>

    <div v-if="error" class="mb-4 rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2.5 text-sm text-red-400">{{ error }}</div>

    <AdminDataTable :loading="loading" :is-empty="filtered.length === 0">
      <template #head>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">데이터셋</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">대상 서비스</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">생성 모델</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">상태</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">문항</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">작업</th>
      </template>

      <template #empty>
        <DatabaseIcon class="mx-auto mb-4 h-12 w-12 text-zinc-700" />
        <h3 class="mb-1 text-sm font-semibold text-zinc-300">생성 데이터셋이 없습니다</h3>
        <p class="text-sm text-zinc-600">대상 서비스 화면에서 데이터셋 생성 탭을 사용하세요.</p>
      </template>

      <tr v-for="dataset in filtered" :key="dataset.id" class="table-row">
        <td class="px-5 py-3.5">
          <p class="font-medium text-zinc-200">{{ dataset.name }}</p>
          <p class="max-w-xs truncate text-xs text-zinc-500">{{ dataset.description || '-' }}</p>
        </td>
        <td class="whitespace-nowrap px-5 py-3.5 text-sm text-zinc-300">{{ dataset.service_feature_name }}</td>
        <td class="whitespace-nowrap px-5 py-3.5 text-sm text-zinc-400">{{ dataset.generation_model_label || '-' }}</td>
        <td class="whitespace-nowrap px-5 py-3.5">
          <span :class="['rounded-md border px-2 py-0.5 text-xs font-medium', statusClass(dataset.status)]">{{ statusLabel(dataset.status) }}</span>
        </td>
        <td class="whitespace-nowrap px-5 py-3.5 text-sm text-zinc-300">
          {{ dataset.question_count.toLocaleString() }} / {{ (dataset.requested_question_count || dataset.question_count).toLocaleString() }}
        </td>
        <td class="whitespace-nowrap px-5 py-3.5">
          <div class="flex items-center gap-1">
            <button class="rounded-md p-1.5 text-zinc-500 transition-colors hover:bg-zinc-700 hover:text-zinc-200" title="미리보기" type="button" @click="selected = dataset"><EyeIcon class="h-4 w-4" /></button>
            <button class="rounded-md p-1.5 text-zinc-500 transition-colors hover:bg-red-900/40 hover:text-red-400" title="삭제" type="button" @click="remove(dataset)"><TrashIcon class="h-4 w-4" /></button>
          </div>
        </td>
      </tr>
    </AdminDataTable>

    <div v-if="selected" class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
      <div class="w-full max-w-3xl rounded-xl border border-zinc-700 bg-zinc-900 shadow-2xl">
        <div class="flex items-center justify-between border-b border-zinc-800 px-6 py-4">
          <div>
            <h3 class="text-base font-semibold text-zinc-100">{{ selected.name }}</h3>
            <p class="mt-0.5 text-xs text-zinc-500">{{ selected.service_feature_name }} · {{ selected.generation_model_label || '-' }}</p>
          </div>
          <button class="rounded-md p-1.5 text-zinc-500 hover:bg-zinc-800 hover:text-zinc-300" type="button" @click="selected = null"><XIcon class="h-4 w-4" /></button>
        </div>
        <div class="space-y-4 p-6">
          <div class="grid grid-cols-3 gap-3">
            <div class="rounded-lg bg-zinc-800/60 p-3">
              <p class="mb-1 text-[10px] font-medium uppercase tracking-wide text-zinc-500">유형</p>
              <p class="text-sm font-semibold text-zinc-200">{{ selected.dataset_type }}</p>
            </div>
            <div class="rounded-lg bg-zinc-800/60 p-3">
              <p class="mb-1 text-[10px] font-medium uppercase tracking-wide text-zinc-500">포맷</p>
              <p class="text-sm font-semibold text-zinc-200">{{ selected.data_format.toUpperCase() }}</p>
            </div>
            <div class="rounded-lg bg-zinc-800/60 p-3">
              <p class="mb-1 text-[10px] font-medium uppercase tracking-wide text-zinc-500">문항 수</p>
              <p class="text-sm font-semibold text-zinc-200">{{ selected.question_count }} / {{ selected.requested_question_count || selected.question_count }}</p>
            </div>
          </div>
          <div v-if="selected.error_message" class="rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2.5 text-sm text-red-300">{{ selected.error_message }}</div>
          <pre class="max-h-[70vh] overflow-auto rounded-lg border border-zinc-800 bg-zinc-950 p-4 text-xs leading-relaxed text-zinc-300">{{ previewContent(selected) }}</pre>
        </div>
      </div>
    </div>
  </div>
</template>
