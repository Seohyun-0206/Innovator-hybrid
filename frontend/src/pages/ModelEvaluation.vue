<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { BarChart3Icon, BeakerIcon, CoinsIcon, GaugeIcon, ListChecksIcon, RouteIcon, SearchIcon, ShieldCheckIcon } from 'lucide-vue-next'
import AdminDataTable from '../components/common/AdminDataTable.vue'
import { EvaluationResult, EvaluationRun, useApi } from '../composables/useApi'

type MetricColumn = {
  key: string
  label: string
  getValue: (result: EvaluationResult) => string
}

const api = useApi()
const runs = ref<EvaluationRun[]>([])
const results = ref<EvaluationResult[]>([])
const loading = ref(false)
const runSearchQuery = ref('')
const modelSearchQuery = ref('')
const selectedRunId = ref<number | null>(null)

const filteredRuns = computed(() => {
  const query = runSearchQuery.value.trim().toLowerCase()
  return [...runs.value]
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .filter(
      (run) =>
        !query ||
        run.name.toLowerCase().includes(query) ||
        run.dataset_name.toLowerCase().includes(query) ||
        run.dataset_type.toLowerCase().includes(query) ||
        (run.evaluation_method_name ?? '').toLowerCase().includes(query) ||
        (run.evaluation_method_type ?? '').toLowerCase().includes(query) ||
        run.status.toLowerCase().includes(query)
    )
})

const selectedRun = computed(() => runs.value.find((run) => run.id === selectedRunId.value) ?? filteredRuns.value[0] ?? null)

const selectedRunResults = computed(() => {
  if (!selectedRun.value) return []
  const embeddedResults = selectedRun.value.results ?? []
  const runResults = embeddedResults.length ? embeddedResults : results.value.filter((result) => result.run === selectedRun.value?.id)
  const query = modelSearchQuery.value.trim().toLowerCase()
  return runResults.filter(
    (result) =>
      !query ||
      result.model_display_name.toLowerCase().includes(query) ||
      result.model_name.toLowerCase().includes(query) ||
      result.model_provider.toLowerCase().includes(query) ||
      result.status.toLowerCase().includes(query)
  )
})

const completedResults = computed(() => selectedRunResults.value.filter((result) => result.status === 'completed'))

const isMultipleChoiceRun = computed(() => {
  const run = selectedRun.value
  const methodType = (run?.evaluation_method_type ?? '').toLowerCase()
  const methodName = (run?.evaluation_method_name ?? '').toLowerCase()
  const datasetType = (run?.dataset_type ?? '').toLowerCase()
  return methodType.includes('multiple_choice') || methodName.includes('mmlu') || datasetType === 'mmlu' || datasetType === 'custom_mcq'
})

const methodDescription = computed(() => {
  if (!selectedRun.value) {
    return {
      title: '실험 실행을 선택하세요',
      body: '왼쪽 목록에서 분석할 실험을 선택하면 해당 실행 안의 모델 결과만 비교합니다.',
    }
  }
  if (isMultipleChoiceRun.value) {
    return {
      title: '객관식/MMLU 계열 분석',
      body: '정확도, strict 준수율, parse 실패율, category/subject 정확도를 우선 확인합니다. 문항별 로그와 선택지/원문 응답은 상세 검증용으로 연결됩니다.',
    }
  }
  return {
    title: '생성형/커스텀 평가 분석',
    body: '공통 metric, 지연 시간, 토큰, 비용, 실패율을 중심으로 비교합니다. scorecard가 없는 평가방식은 별도 점수 카드 없이 관측 가능한 지표만 표시합니다.',
  }
})

const averageAccuracy = computed(() => average(completedResults.value.map((result) => toNumber(result.overall_accuracy)).filter(isFiniteNumber)))
const averageP95Latency = computed(() => average(completedResults.value.map((result) => result.latency_p95_ms).filter(isFiniteNumber)))
const averageFailureRate = computed(() => average(selectedRunResults.value.map((result) => toNumber(result.failure_rate)).filter(isFiniteNumber)))
const totalTokens = computed(() => selectedRunResults.value.reduce((sum, result) => sum + (result.input_tokens || 0) + (result.output_tokens || 0), 0))
const totalCost = computed(() => selectedRunResults.value.reduce((sum, result) => sum + Number(result.estimated_cost_usd ?? 0), 0))

const overviewCards = computed(() => [
  {
    label: '완료 모델',
    value: `${completedResults.value.length}/${selectedRunResults.value.length}`,
    sub: selectedRun.value ? `${selectedRun.value.name} 기준` : '실험을 선택하세요',
    icon: BarChart3Icon,
  },
  {
    label: '평균 정확도',
    value: averageAccuracy.value === null ? '-' : formatPercentNumber(averageAccuracy.value),
    sub: isMultipleChoiceRun.value ? '정답 기반 metric' : '제공될 때만 계산',
    icon: ShieldCheckIcon,
  },
  {
    label: '평균 p95 지연',
    value: averageP95Latency.value === null ? '-' : `${Math.round(averageP95Latency.value)}ms`,
    sub: '완료 결과 p95 평균',
    icon: GaugeIcon,
  },
  {
    label: '토큰 / 비용',
    value: `${formatCompactNumber(totalTokens.value)} tok`,
    sub: formatCostNumber(totalCost.value),
    icon: CoinsIcon,
  },
])

const scorecardMetricKeys = computed(() => {
  const excluded = new Set(['recommended_role'])
  const keys = new Set<string>()
  selectedRunResults.value.forEach((result) => {
    Object.entries(result.scorecard ?? {}).forEach(([key, value]) => {
      if (!excluded.has(key) && (typeof value === 'number' || typeof value === 'string')) {
        keys.add(key)
      }
    })
  })
  return [...keys].slice(0, 4)
})

const hasScorecardMetrics = computed(() => scorecardMetricKeys.value.length > 0)

const metricColumns = computed<MetricColumn[]>(() => {
  const columns: MetricColumn[] = [
    { key: 'accuracy', label: '정확도', getValue: (result) => formatPercent(result.overall_accuracy) },
    { key: 'latency', label: '지연 p50/p95', getValue: (result) => `${formatMs(result.latency_p50_ms)} / ${formatMs(result.latency_p95_ms)}` },
    { key: 'tokens', label: '토큰/비용', getValue: (result) => `${formatCompactNumber((result.input_tokens || 0) + (result.output_tokens || 0))} tok · ${formatCost(result.estimated_cost_usd)}` },
    { key: 'failure', label: '실패율', getValue: (result) => formatPercent(result.failure_rate) },
  ]

  if (isMultipleChoiceRun.value) {
    columns.splice(1, 0, { key: 'strict', label: 'Strict', getValue: (result) => formatPercent(result.strict_compliance_rate) })
    columns.splice(2, 0, { key: 'parse_failure', label: 'Parse 실패', getValue: (result) => formatPercent(result.parse_failure_rate) })
  }

  scorecardMetricKeys.value.forEach((key) => {
    columns.push({
      key: `scorecard-${key}`,
      label: formatMetricLabel(key),
      getValue: (result) => formatUnknownMetric(result.scorecard?.[key]),
    })
  })

  return columns
})

const fastestResult = computed(() =>
  [...completedResults.value]
    .filter((result) => result.latency_p95_ms !== null)
    .sort((a, b) => (a.latency_p95_ms ?? Number.MAX_SAFE_INTEGER) - (b.latency_p95_ms ?? Number.MAX_SAFE_INTEGER))[0]
)

const mostAccurateResult = computed(() =>
  [...completedResults.value]
    .filter((result) => result.overall_accuracy !== null)
    .sort((a, b) => Number(b.overall_accuracy ?? 0) - Number(a.overall_accuracy ?? 0))[0]
)

const mostReliableResult = computed(() =>
  [...selectedRunResults.value]
    .filter((result) => result.failure_rate !== null)
    .sort((a, b) => Number(a.failure_rate ?? 1) - Number(b.failure_rate ?? 1))[0]
)

const categoryHighlights = computed(() => collectAccuracyHighlights('category_accuracy'))
const subjectHighlights = computed(() => collectAccuracyHighlights('subject_accuracy'))

async function loadPageData() {
  loading.value = true
  try {
    const [loadedRuns, loadedResults] = await Promise.all([api.getEvaluationRuns(), api.getEvaluationResults()])
    runs.value = loadedRuns
    results.value = loadedResults
    const storedRunId = sessionStorage.getItem('selected-evaluation-run-id')
    if (storedRunId) {
      const parsedId = Number(storedRunId)
      if (loadedRuns.some((run) => run.id === parsedId)) {
        selectedRunId.value = parsedId
      }
      sessionStorage.removeItem('selected-evaluation-run-id')
    }
    selectedRunId.value = selectedRunId.value ?? loadedRuns[0]?.id ?? null
  } finally {
    loading.value = false
  }
}

function selectRun(runId: number) {
  selectedRunId.value = runId
  modelSearchQuery.value = ''
}

function toNumber(value: string | number | null) {
  if (value === null) return null
  const numberValue = Number(value)
  return Number.isFinite(numberValue) ? numberValue : null
}

function isFiniteNumber(value: number | null): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

function average(values: number[]) {
  if (!values.length) return null
  return values.reduce((sum, value) => sum + value, 0) / values.length
}

function formatPercent(value: string | number | null) {
  const numberValue = toNumber(value)
  if (numberValue === null) return '-'
  return formatPercentNumber(numberValue)
}

function formatPercentNumber(value: number) {
  return `${Math.round(value * 100)}%`
}

function formatCost(value: string | null) {
  if (value === null) return '-'
  return formatCostNumber(Number(value))
}

function formatCostNumber(value: number) {
  return `$${Number(value || 0).toFixed(6)}`
}

function formatCompactNumber(value: number) {
  return new Intl.NumberFormat('ko-KR', { notation: value >= 10000 ? 'compact' : 'standard' }).format(value || 0)
}

function formatMs(value: number | null) {
  return value === null ? '-' : `${value}ms`
}

function formatMetricLabel(key: string) {
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase())
}

function formatUnknownMetric(value: unknown) {
  if (value === null || value === undefined || value === '') return '-'
  if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(3)
  if (typeof value === 'string') return value
  return '-'
}

function getRole(result: EvaluationResult) {
  const role = result.scorecard?.recommended_role
  return typeof role === 'string' ? role : recommendRole(result)
}

function recommendRole(result: EvaluationResult) {
  const accuracy = Number(result.overall_accuracy ?? 0)
  const failureRate = Number(result.failure_rate ?? 0)
  if (failureRate > 0.25) return 'Escalation Candidate'
  if (accuracy >= 0.8) return 'Accurate Path'
  if ((result.latency_p95_ms ?? Number.MAX_SAFE_INTEGER) <= 3000 && (result.overall_accuracy === null || accuracy >= 0.55)) return 'Fast Path'
  return 'Review Needed'
}

function roleClass(role: string) {
  if (role === 'Accurate Path') return 'badge-primary'
  if (role === 'Fast Path') return 'badge-success'
  if (role === 'Escalation Candidate') return 'badge-warning'
  return 'badge-muted'
}

function getStatusLabel(status: string) {
  if (status === 'pending') return '대기'
  if (status === 'running') return '실행 중'
  if (status === 'completed') return '완료'
  if (status === 'failed') return '실패'
  return status
}

function statusClass(status: string) {
  if (status === 'completed') return 'badge-success'
  if (status === 'failed') return 'badge-danger'
  if (status === 'running') return 'badge-primary'
  return 'badge-warning'
}

function getDatasetTypeLabel(type: string) {
  if (type === 'multiple_choice') return '객관식 평가'
  if (type === 'qa') return 'QA'
  if (type === 'generation') return '생성/요약'
  if (type === 'rag') return 'RAG'
  if (type === 'safety_classification') return '안전성/분류'
  if (type === 'custom') return '기타/사용자 정의'
  if (type === 'mmlu') return 'MMLU'
  if (type === 'custom_mcq') return '객관식 커스텀'
  if (type === 'jsonl') return 'JSONL'
  if (type === 'csv') return 'CSV'
  return type
}

function formatDate(value: string | null) {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}

function collectAccuracyHighlights(field: 'category_accuracy' | 'subject_accuracy') {
  const pairs = new Map<string, number[]>()
  completedResults.value.forEach((result) => {
    Object.entries(result[field] ?? {}).forEach(([name, value]) => {
      const numberValue = toNumber(value as string | number | null)
      if (numberValue !== null) {
        pairs.set(name, [...(pairs.get(name) ?? []), numberValue])
      }
    })
  })
  return [...pairs.entries()]
    .map(([name, values]) => ({ name, value: average(values) ?? 0 }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 5)
}

watch(filteredRuns, (nextRuns) => {
  if (!nextRuns.length) {
    selectedRunId.value = null
    return
  }
  if (!nextRuns.some((run) => run.id === selectedRunId.value)) {
    selectedRunId.value = nextRuns[0].id
  }
})

onMounted(loadPageData)
</script>

<template>
  <div class="page-shell">
    <div class="page-header">
      <div>
        <p class="page-label">실험 분석</p>
        <h2 class="page-title">결과 분석</h2>
        <p class="page-subtitle">실험 실행을 선택한 뒤, 같은 데이터셋과 평가방식 안에서 모델별 결과를 비교합니다.</p>
      </div>
    </div>

    <section class="mb-6 grid gap-4 xl:grid-cols-[22rem_minmax(0,1fr)]">
      <aside class="section-card-padded">
        <div class="mb-4">
          <p class="mb-2 text-xs font-semibold uppercase tracking-widest text-zinc-500">실험 선택</p>
          <div class="relative">
            <SearchIcon class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
            <input
              v-model="runSearchQuery"
              class="w-full rounded-lg border border-zinc-700 bg-zinc-800 py-2.5 pl-9 pr-4 text-sm text-zinc-200 placeholder-zinc-600 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50"
              placeholder="실행명, 데이터셋, 평가방식 검색..."
              type="text"
            />
          </div>
        </div>

        <div class="max-h-[32rem] space-y-2 overflow-y-auto pr-1">
          <button
            v-for="run in filteredRuns"
            :key="run.id"
          :class="[
            'list-item w-full px-3 py-3 text-left transition',
            selectedRun?.id === run.id ? 'list-item-selected' : 'list-item-hover'
          ]"
            type="button"
            @click="selectRun(run.id)"
          >
            <div class="mb-1 flex items-center justify-between gap-2">
              <p class="truncate text-sm font-semibold text-zinc-100">{{ run.name }}</p>
              <span :class="['badge shrink-0', statusClass(run.status)]">{{ getStatusLabel(run.status) }}</span>
            </div>
            <p class="truncate text-xs text-zinc-500">{{ run.dataset_name }} · {{ getDatasetTypeLabel(run.dataset_type) }}</p>
            <p class="mt-1 truncate text-xs text-zinc-600">{{ run.evaluation_method_name || '평가방식 미지정' }} · {{ formatDate(run.created_at) }}</p>
          </button>
          <p v-if="!filteredRuns.length && !loading" class="rounded-lg border border-zinc-800 bg-zinc-950/40 px-3 py-6 text-center text-sm text-zinc-600">
            조건에 맞는 실험 실행이 없습니다.
          </p>
        </div>
      </aside>

      <div class="space-y-4">
        <div class="section-card-padded">
          <div class="mb-4 flex flex-wrap items-start justify-between gap-3">
            <div>
              <p class="text-xs font-semibold uppercase tracking-widest text-zinc-500">선택된 실행</p>
              <h3 class="mt-1 text-xl font-bold text-zinc-100">{{ selectedRun?.name ?? '실험 실행 없음' }}</h3>
              <p class="mt-1 text-sm text-zinc-500">
                {{ selectedRun?.dataset_name ?? '-' }} · {{ selectedRun ? getDatasetTypeLabel(selectedRun.dataset_type) : '-' }} ·
                {{ selectedRun?.evaluation_method_name ?? '평가방식 미지정' }}
              </p>
            </div>
            <span v-if="selectedRun" :class="['badge', statusClass(selectedRun.status)]">{{ getStatusLabel(selectedRun.status) }}</span>
          </div>
          <div class="subsection-card">
            <div class="mb-2 flex items-center gap-2">
              <ListChecksIcon class="h-4 w-4 text-indigo-400" />
              <p class="text-sm font-semibold text-zinc-200">{{ methodDescription.title }}</p>
            </div>
            <p class="text-sm leading-6 text-zinc-500">{{ methodDescription.body }}</p>
          </div>
        </div>

        <section class="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <div v-for="card in overviewCards" :key="card.label" class="section-card-padded">
            <div class="mb-3 flex items-center justify-between">
              <p class="text-xs font-semibold uppercase tracking-widest text-zinc-500">{{ card.label }}</p>
              <component :is="card.icon" class="h-4 w-4 text-indigo-400" />
            </div>
            <p class="text-2xl font-bold text-zinc-100">{{ card.value }}</p>
            <p class="mt-1 text-xs text-zinc-500">{{ card.sub }}</p>
          </div>
        </section>
      </div>
    </section>

    <section v-if="selectedRun" class="mb-6 grid gap-4 xl:grid-cols-3">
      <div class="section-card-padded">
        <p class="mb-2 text-xs font-semibold uppercase tracking-widest text-zinc-500">평균 실패율</p>
        <p class="text-lg font-semibold text-zinc-100">{{ averageFailureRate === null ? '-' : formatPercentNumber(averageFailureRate) }}</p>
        <p class="mt-1 text-sm text-zinc-500">실행 안의 모델 결과 기준</p>
      </div>
      <div class="section-card-padded">
        <p class="mb-2 text-xs font-semibold uppercase tracking-widest text-zinc-500">가장 빠른 모델</p>
        <p class="text-lg font-semibold text-zinc-100">{{ fastestResult?.model_display_name ?? '-' }}</p>
        <p class="mt-1 text-sm text-zinc-500">p95 {{ fastestResult?.latency_p95_ms ?? '-' }}ms · 실패 {{ formatPercent(fastestResult?.failure_rate ?? null) }}</p>
      </div>
      <div class="section-card-padded">
        <p class="mb-2 text-xs font-semibold uppercase tracking-widest text-zinc-500">가장 안정적인 모델</p>
        <p class="text-lg font-semibold text-zinc-100">{{ mostReliableResult?.model_display_name ?? '-' }}</p>
        <p class="mt-1 text-sm text-zinc-500">실패 {{ formatPercent(mostReliableResult?.failure_rate ?? null) }} · 정확도 {{ formatPercent(mostReliableResult?.overall_accuracy ?? null) }}</p>
      </div>
    </section>

    <section v-if="selectedRun && isMultipleChoiceRun" class="mb-6 grid gap-4 lg:grid-cols-2">
      <div class="section-card-padded">
        <p class="mb-3 text-sm font-semibold text-zinc-200">Category 정확도 상위</p>
        <div class="space-y-2">
          <div v-for="item in categoryHighlights" :key="item.name" class="flex items-center justify-between rounded-lg bg-zinc-800/50 px-3 py-2 text-sm">
            <span class="truncate text-zinc-300">{{ item.name }}</span>
            <span class="text-zinc-400">{{ formatPercentNumber(item.value) }}</span>
          </div>
          <p v-if="!categoryHighlights.length" class="text-sm text-zinc-600">category accuracy 데이터가 없습니다.</p>
        </div>
      </div>
      <div class="section-card-padded">
        <p class="mb-3 text-sm font-semibold text-zinc-200">Subject 정확도 상위</p>
        <div class="space-y-2">
          <div v-for="item in subjectHighlights" :key="item.name" class="flex items-center justify-between rounded-lg bg-zinc-800/50 px-3 py-2 text-sm">
            <span class="truncate text-zinc-300">{{ item.name }}</span>
            <span class="text-zinc-400">{{ formatPercentNumber(item.value) }}</span>
          </div>
          <p v-if="!subjectHighlights.length" class="text-sm text-zinc-600">subject accuracy 데이터가 없습니다.</p>
        </div>
      </div>
    </section>

    <details v-if="selectedRun" class="section-card-padded mb-6 border-indigo-500/20 bg-indigo-500/10">
      <summary class="flex cursor-pointer list-none items-center gap-2 text-sm font-semibold text-indigo-300">
        <RouteIcon class="h-4 w-4" />
        정책 설계 보조 정보 보기
      </summary>
      <div class="mt-4 grid gap-4 md:grid-cols-3">
        <div class="rounded-lg border border-indigo-500/20 bg-zinc-950/30 p-4">
          <p class="text-xs font-semibold uppercase tracking-widest text-indigo-300">Fast Path 참고</p>
          <p class="mt-2 text-sm font-semibold text-zinc-100">{{ fastestResult?.model_display_name ?? '-' }}</p>
          <p class="mt-1 text-xs text-zinc-500">낮은 p95 지연과 허용 가능한 실패율을 볼 때 참고합니다.</p>
        </div>
        <div class="rounded-lg border border-indigo-500/20 bg-zinc-950/30 p-4">
          <p class="text-xs font-semibold uppercase tracking-widest text-indigo-300">Accurate Path 참고</p>
          <p class="mt-2 text-sm font-semibold text-zinc-100">{{ mostAccurateResult?.model_display_name ?? '-' }}</p>
          <p class="mt-1 text-xs text-zinc-500">정확도 metric이 있는 평가에서만 의미 있게 해석합니다.</p>
        </div>
        <div class="rounded-lg border border-indigo-500/20 bg-zinc-950/30 p-4">
          <p class="text-xs font-semibold uppercase tracking-widest text-indigo-300">Escalation 참고</p>
          <p class="mt-2 text-sm font-semibold text-zinc-100">{{ selectedRunResults.filter((result) => getRole(result) === 'Escalation Candidate').length }}개 모델</p>
          <p class="mt-1 text-xs text-zinc-500">정책 후보가 필요할 때만 보조 자료로 사용하세요.</p>
        </div>
      </div>
    </details>

    <div class="mb-5 flex flex-wrap items-center gap-3">
      <div class="relative min-w-72 flex-1">
        <SearchIcon class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
        <input
          v-model="modelSearchQuery"
          class="ui-input-search"
          placeholder="선택 실행 안에서 모델, provider, 상태 검색..."
          type="text"
        />
      </div>
    </div>

    <AdminDataTable :loading="loading" :is-empty="selectedRunResults.length === 0">
      <template #head>
        <th class="table-th">모델</th>
        <th class="table-th">Provider</th>
        <th class="table-th">상태</th>
        <th v-for="column in metricColumns" :key="column.key" class="table-th">
          {{ column.label }}
        </th>
        <th class="table-th">문항/로그</th>
        <th v-if="hasScorecardMetrics" class="table-th">Scorecard 역할</th>
      </template>

      <template #empty>
        <BeakerIcon class="empty-icon" />
        <h3 class="empty-title">선택된 실험의 결과가 없습니다</h3>
        <p class="empty-description">실험 실행을 생성하고 실행한 뒤, 이 화면에서 실행별 모델 비교를 확인하세요.</p>
      </template>

      <tr v-for="result in selectedRunResults" :key="result.id" class="table-row">
        <td class="px-5 py-3.5">
          <p class="font-medium text-zinc-200">{{ result.model_display_name }}</p>
          <p class="text-xs text-zinc-500">{{ result.model_name }}</p>
        </td>
        <td class="whitespace-nowrap px-5 py-3.5 text-sm capitalize text-zinc-300">{{ result.model_provider }}</td>
        <td class="whitespace-nowrap px-5 py-3.5">
          <span :class="['badge', statusClass(result.status)]">{{ getStatusLabel(result.status) }}</span>
        </td>
        <td v-for="column in metricColumns" :key="`${result.id}-${column.key}`" class="whitespace-nowrap px-5 py-3.5 text-sm text-zinc-300">
          {{ column.getValue(result) }}
        </td>
        <td class="whitespace-nowrap px-5 py-3.5 text-sm text-zinc-300">
          <p>{{ result.item_result_count || 0 }}개</p>
          <p class="text-xs text-zinc-500">{{ isMultipleChoiceRun ? 'choices/raw logs 확인' : 'raw output/artifact 확인' }}</p>
        </td>
        <td v-if="hasScorecardMetrics" class="whitespace-nowrap px-5 py-3.5">
          <span :class="['badge', roleClass(getRole(result))]">{{ getRole(result) }}</span>
        </td>
      </tr>
    </AdminDataTable>
  </div>
</template>
