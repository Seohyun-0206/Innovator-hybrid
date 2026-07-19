<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { FileSearchIcon, SearchIcon } from 'lucide-vue-next'
import AdminDataTable from '../components/common/AdminDataTable.vue'
import AppSelect, { SelectOption } from '../components/common/AppSelect.vue'
import { EvaluationItemResult, EvaluationRun, useApi } from '../composables/useApi'

const api = useApi()
const runs = ref<EvaluationRun[]>([])
const items = ref<EvaluationItemResult[]>([])
const selectedRun = ref('')
const selectedResult = ref('')
const searchQuery = ref('')
const loading = ref(false)

const runOptions = computed<SelectOption[]>(() => [
  { value: '', label: '전체 실행' },
  ...runs.value.map((run) => ({ value: String(run.id), label: `${run.name} (#${run.id})` })),
])

const resultOptions = computed<SelectOption[]>(() => {
  const run = runs.value.find((item) => item.id === Number(selectedRun.value))
  const results = run?.results ?? []
  return [
    { value: '', label: '전체 결과' },
    ...results.map((result) => ({
      value: String(result.id),
      label: `${result.result_type === 'routing' ? result.candidate_label : result.model_display_name} · ${result.status}`,
    })),
  ]
})

const filteredItems = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()
  return items.value.filter(
    (item) =>
      !query ||
      item.question.toLowerCase().includes(query) ||
      (item.model_display_name ?? '').toLowerCase().includes(query) ||
      item.dataset_name.toLowerCase().includes(query) ||
      item.subject.toLowerCase().includes(query) ||
      item.category.toLowerCase().includes(query) ||
      item.raw_output.toLowerCase().includes(query) ||
      item.router_output.toLowerCase().includes(query) ||
      item.error.toLowerCase().includes(query)
  )
})

const hasRouterOutputs = computed(() => filteredItems.value.some((item) => item.router_output))

async function loadRuns() {
  runs.value = await api.getEvaluationRuns()
}

async function loadItems() {
  loading.value = true
  try {
    items.value = await api.getEvaluationItemResults({
      run: selectedRun.value ? Number(selectedRun.value) : undefined,
      result: selectedResult.value ? Number(selectedResult.value) : undefined,
    })
  } finally {
    loading.value = false
  }
}

function statusClass(item: EvaluationItemResult) {
  if (item.is_correct) return 'badge-success'
  if (item.ok) return 'badge-warning'
  return 'badge-danger'
}

function formatChoices(choices: string[]) {
  return choices.slice(0, 4).map((choice, index) => `${String.fromCharCode(65 + index)}. ${choice}`).join('\n')
}

watch(selectedRun, () => {
  selectedResult.value = ''
  loadItems()
})
watch(selectedResult, loadItems)

onMounted(async () => {
  await loadRuns()
  await loadItems()
})
</script>

<template>
  <div class="page-shell">
    <div class="mb-6">
      <p class="page-label">실험</p>
      <h2 class="page-title">문항별 로그</h2>
      <p class="page-subtitle">평가 실행의 각 문항 응답과 retry 시도, strict 준수, 오류, 지연시간을 확인합니다.</p>
    </div>

    <div class="mb-5 grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(18rem,2fr)]">
      <AppSelect v-model="selectedRun" :options="runOptions" />
      <AppSelect v-model="selectedResult" :options="resultOptions" />
      <div class="relative">
        <SearchIcon class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
        <input v-model="searchQuery" class="ui-input-search" placeholder="문항, 모델, subject, raw output 검색..." type="text" />
      </div>
    </div>

    <AdminDataTable :loading="loading" :is-empty="filteredItems.length === 0">
      <template #head>
        <th class="table-th">문항</th>
        <th class="table-th">모델</th>
        <th class="table-th">정답/예측</th>
        <th class="table-th">상태</th>
        <th class="table-th">토큰/지연</th>
        <th v-if="hasRouterOutputs" class="table-th">Router Output</th>
        <th class="table-th">Raw Output</th>
      </template>
      <template #empty>
        <FileSearchIcon class="empty-icon" />
        <h3 class="empty-title">문항별 로그가 없습니다</h3>
        <p class="empty-description">실험 목록에서 파일럿 자동 평가를 실행하면 문항별 로그가 저장됩니다.</p>
      </template>
      <tr v-for="item in filteredItems" :key="item.id" class="table-row align-top">
        <td class="px-5 py-3.5">
          <p class="text-xs text-zinc-500">#{{ item.item_index }} · attempt {{ item.attempt }}</p>
          <p class="mt-1 max-w-xl text-sm text-zinc-200">{{ item.question }}</p>
          <pre class="code-panel mt-2 whitespace-pre-wrap rounded p-2 text-zinc-500">{{ formatChoices(item.choices) }}</pre>
          <p class="mt-1 text-xs text-zinc-500">{{ item.subject || 'subject 없음' }} · {{ item.category || 'category 없음' }}</p>
        </td>
        <td class="px-5 py-3.5">
          <p class="font-medium text-zinc-200">{{ item.model_display_name }}</p>
          <p class="text-xs text-zinc-500">{{ item.model_provider }}/{{ item.model_name }}</p>
          <p class="text-xs text-zinc-500">{{ item.result_run_name }}</p>
        </td>
        <td class="whitespace-nowrap px-5 py-3.5 text-sm text-zinc-300">
          <p>Gold: <span class="font-semibold text-zinc-100">{{ item.gold || '-' }}</span></p>
          <p>Pred: <span class="font-semibold text-zinc-100">{{ item.predicted_choice || '-' }}</span></p>
          <p class="mt-1 text-xs text-zinc-500">Strict: {{ item.strict_ok ? 'Y' : 'N' }}</p>
        </td>
        <td class="whitespace-nowrap px-5 py-3.5">
          <span :class="['badge', statusClass(item)]">
            {{ item.is_correct ? '정답' : item.ok ? '오답' : '실패' }}
          </span>
          <p v-if="item.error" class="mt-2 max-w-xs whitespace-normal text-xs text-red-400">{{ item.error }}</p>
        </td>
        <td class="whitespace-nowrap px-5 py-3.5 text-sm text-zinc-300">
          <p>{{ item.input_tokens }} / {{ item.output_tokens }} tok</p>
          <p class="text-xs text-zinc-500">{{ item.latency_ms ?? '-' }}ms</p>
        </td>
        <td v-if="hasRouterOutputs" class="px-5 py-3.5">
          <pre v-if="item.router_output" class="code-panel max-h-32 max-w-xs whitespace-pre-wrap rounded p-2">{{ item.router_output }}</pre>
          <span v-else class="text-xs text-zinc-600">-</span>
        </td>
        <td class="px-5 py-3.5">
          <pre class="code-panel max-h-32 max-w-md whitespace-pre-wrap rounded p-2">{{ item.raw_output || '-' }}</pre>
        </td>
      </tr>
    </AdminDataTable>
  </div>
</template>
