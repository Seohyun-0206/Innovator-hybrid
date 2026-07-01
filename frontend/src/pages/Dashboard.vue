<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import {
  ActivityIcon,
  BarChart3Icon,
  BotIcon,
  CheckCircle2Icon,
  ClipboardListIcon,
  CpuIcon,
  DatabaseIcon,
  FlaskConicalIcon,
  ServerIcon,
  XCircleIcon
} from 'lucide-vue-next'
import { DashboardMetrics, EvaluationDataset, EvaluationMethod, EvaluationResult, EvaluationRun, LLMModel, useApi } from '../composables/useApi'

const api = useApi()
const metrics = ref<DashboardMetrics | null>(null)
const runs = ref<EvaluationRun[]>([])
const models = ref<LLMModel[]>([])
const datasets = ref<EvaluationDataset[]>([])
const methods = ref<EvaluationMethod[]>([])
const results = ref<EvaluationResult[]>([])
const loading = ref(true)
const period = ref('7d')
const customStartDate = ref('')
const customEndDate = ref('')

const experimentMetrics = computed(() => metrics.value?.experiment_metrics ?? null)

const runStatusCounts = computed(() => ({
  total: runs.value.length,
  completed: runs.value.filter((run) => run.status === 'completed').length,
  running: runs.value.filter((run) => run.status === 'running').length,
  failed: runs.value.filter((run) => run.status === 'failed').length,
}))

const recentRuns = computed(() =>
  [...runs.value]
    .sort((a, b) => new Date(b.updated_at || b.created_at).getTime() - new Date(a.updated_at || a.created_at).getTime())
    .slice(0, 5)
)

const selectedRecentRunId = ref<number | null>(null)

const selectedRecentRun = computed(
  () => recentRuns.value.find((run) => run.id === selectedRecentRunId.value) ?? recentRuns.value[0] ?? null
)

function buildRunSummary(run: EvaluationRun) {
  const runResults = getRunResults(run)
  const completedResults = runResults.filter((result) => result.status === 'completed')
  const accuracy = average(completedResults.map((result) => toNumber(result.overall_accuracy)).filter(isFiniteNumber))
  const latency = average(completedResults.map((result) => result.latency_p95_ms).filter(isFiniteNumber))
  const cost = runResults.reduce((sum, result) => sum + Number(result.estimated_cost_usd ?? 0), 0)
  return {
    run,
    completedModels: completedResults.length,
    totalModels: runResults.length,
    accuracy,
    latency,
    cost,
  }
}

const selectedRecentRunSummary = computed(() => {
  const run = selectedRecentRun.value
  return run ? buildRunSummary(run) : null
})

const platformCards = computed(() => [
  {
    label: '전체 실험',
    value: String(runStatusCounts.value.total),
    sub: `완료 ${runStatusCounts.value.completed} · 실행 중 ${runStatusCounts.value.running} · 실패 ${runStatusCounts.value.failed}`,
    icon: FlaskConicalIcon,
  },
  {
    label: '등록 모델',
    value: String(models.value.length),
    sub: `활성 ${models.value.filter((model) => model.is_active).length}개`,
    icon: BotIcon,
  },
  {
    label: '데이터셋',
    value: String(datasets.value.length),
    sub: `${datasets.value.reduce((sum, dataset) => sum + (dataset.question_count || 0), 0)}개 문항`,
    icon: DatabaseIcon,
  },
  {
    label: '평가방식',
    value: String(methods.value.length),
    sub: `활성 ${methods.value.filter((method) => method.is_active).length}개`,
    icon: ClipboardListIcon,
  },
])

function formatUsd(value: string | number) {
  return `$${Number(value || 0).toFixed(6)}`
}

function formatPercent(value: number) {
  return `${Math.round((value || 0) * 100)}%`
}

function dateToInputValue(date: Date) {
  return date.toISOString().slice(0, 10)
}

function setDefaultCustomDates() {
  if (customStartDate.value && customEndDate.value) {
    return
  }
  const end = new Date()
  const start = new Date()
  start.setDate(end.getDate() - 6)
  customStartDate.value = dateToInputValue(start)
  customEndDate.value = dateToInputValue(end)
}

async function loadDashboardData() {
  loading.value = true
  try {
    const [loadedMetrics, loadedRuns, loadedModels, loadedDatasets, loadedMethods, loadedResults] = await Promise.all([
      api.getMetrics({
        period: period.value,
        startDate: period.value === 'custom' ? customStartDate.value : undefined,
        endDate: period.value === 'custom' ? customEndDate.value : undefined
      }),
      api.getEvaluationRuns(),
      api.getModels(),
      api.getEvaluationDatasets(),
      api.getEvaluationMethods(),
      api.getEvaluationResults(),
    ])
    metrics.value = loadedMetrics
    runs.value = loadedRuns
    models.value = loadedModels
    datasets.value = loadedDatasets
    methods.value = loadedMethods
    results.value = loadedResults
    if (!recentRuns.value.some((run) => run.id === selectedRecentRunId.value)) {
      selectedRecentRunId.value = recentRuns.value[0]?.id ?? null
    }
  } finally {
    loading.value = false
  }
}

watch(period, () => {
  if (period.value === 'custom') {
    setDefaultCustomDates()
    return
  }
  void loadDashboardData()
})

function getRunResults(run: EvaluationRun) {
  return run.results?.length ? run.results : results.value.filter((result) => result.run === run.id)
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

function formatOptionalPercent(value: number | null) {
  return value === null ? '-' : formatPercent(value)
}

function formatOptionalMs(value: number | null) {
  return value === null ? '-' : `${Math.round(value)}ms`
}

function formatDate(value: string | null) {
  if (!value) return '-'
  return new Date(value).toLocaleString()
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
  return type
}

function selectRecentRun(runId: number) {
  selectedRecentRunId.value = runId
}

function connectivityStatusLabel(status: string) {
  if (status === 'online') return '사용 가능'
  if (status === 'offline') return '모델 없음'
  if (status === 'error') return '연결 오류'
  if (status === 'skipped') return '비활성'
  return status
}

function connectivityStatusClass(status: string) {
  if (status === 'online') return 'badge-success'
  if (status === 'offline') return 'badge-warning'
  if (status === 'error') return 'badge-danger'
  return 'badge-warning'
}

function openWorkspaceTab(tabId: string) {
  window.dispatchEvent(new CustomEvent('open-workspace-tab', { detail: tabId }))
}

onMounted(async () => {
  await loadDashboardData()
})
</script>

<template>
  <div class="p-6 lg:p-8">
    <div class="mb-8 flex flex-wrap items-end justify-between gap-4">
      <div>
        <p class="mb-1 text-xs font-semibold uppercase tracking-widest text-indigo-400">실험 플랫폼</p>
        <h2 class="text-2xl font-bold text-zinc-100">대시보드</h2>
        <p class="mt-1 text-sm text-zinc-500">평가 실험, 리소스, 최근 결과를 한곳에서 확인하고 다음 작업으로 이동합니다.</p>
      </div>

      <div class="flex flex-wrap items-center gap-3">
        <label class="flex items-center gap-2 text-sm text-zinc-500">
          실험 지표 기간
          <select
            v-model="period"
            class="rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-sm text-zinc-200 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50"
          >
            <option value="today">오늘</option>
            <option value="7d">최근 7일</option>
            <option value="30d">최근 30일</option>
            <option value="all">전체</option>
            <option value="custom">직접 선택</option>
          </select>
        </label>

        <template v-if="period === 'custom'">
          <input
            v-model="customStartDate"
            class="rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-sm text-zinc-200 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50"
            type="date"
          />
          <input
            v-model="customEndDate"
            class="rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-sm text-zinc-200 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50"
            type="date"
          />
          <button
            class="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="!customStartDate || !customEndDate || loading"
            type="button"
            @click="loadDashboardData"
          >
            적용
          </button>
        </template>
      </div>
    </div>

    <div v-if="loading" class="flex items-center gap-3 text-zinc-500">
      <div class="h-4 w-4 animate-spin rounded-full border-2 border-zinc-700 border-t-indigo-500"></div>
      <span class="text-sm">대시보드 데이터를 불러오는 중...</span>
    </div>

    <div v-else-if="metrics" class="space-y-6">
      <section class="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <div v-for="card in platformCards" :key="card.label" class="rounded-xl border border-zinc-800 bg-zinc-900 p-5">
          <div class="mb-3 flex items-center justify-between">
            <span class="text-xs font-semibold uppercase tracking-widest text-zinc-500">{{ card.label }}</span>
            <div class="rounded-md bg-indigo-600/10 p-1.5">
              <component :is="card.icon" class="h-3.5 w-3.5 text-indigo-400" />
            </div>
          </div>
          <p class="text-2xl font-bold text-zinc-100">{{ card.value }}</p>
          <p class="mt-1 text-xs text-zinc-500">{{ card.sub }}</p>
        </div>
      </section>

      <section class="grid gap-4 xl:grid-cols-[minmax(0,1fr)_24rem]">
        <div class="section-card-padded">
          <div class="mb-4 flex items-center justify-between gap-3">
            <div>
              <p class="mb-1 text-xs font-semibold uppercase tracking-widest text-zinc-500">실험 요약</p>
              <h3 class="text-sm font-semibold text-zinc-200">최근 실험</h3>
              <p class="mt-1 text-xs text-zinc-500">실행 상태와 결과 생성 흐름을 빠르게 확인합니다.</p>
            </div>
            <button
              class="btn-soft-primary"
              type="button"
              @click="openWorkspaceTab('evaluation-runs')"
            >
              새 실험 만들기
            </button>
          </div>
          <div class="space-y-2">
            <button
              v-for="run in recentRuns"
              :key="run.id"
              :class="[
                'list-item w-full px-3 py-3 text-left transition',
                selectedRecentRun?.id === run.id ? 'list-item-selected' : 'list-item-hover'
              ]"
              type="button"
              @click="selectRecentRun(run.id)"
            >
              <div class="mb-1 flex items-center justify-between gap-2">
                <p class="truncate text-sm font-semibold text-zinc-100">{{ run.name }}</p>
                <span :class="['badge shrink-0', statusClass(run.status)]">{{ getStatusLabel(run.status) }}</span>
              </div>
              <p class="truncate text-xs text-zinc-500">{{ run.dataset_name }} · {{ getDatasetTypeLabel(run.dataset_type) }}</p>
              <p class="mt-1 truncate text-xs text-zinc-600">{{ run.evaluation_method_name || '평가방식 미지정' }} · {{ formatDate(run.updated_at) }}</p>
            </button>
            <p v-if="!recentRuns.length" class="rounded-lg border border-zinc-800 bg-zinc-950/40 px-3 py-8 text-center text-sm text-zinc-600">
              아직 등록된 실험이 없습니다.
            </p>
          </div>
        </div>

        <div class="space-y-4">
          <div class="section-card-padded">
            <div class="mb-3 flex items-start justify-between gap-3">
              <div class="flex items-center gap-2">
                <BarChart3Icon class="h-4 w-4 text-indigo-400" />
                <h3 class="text-sm font-semibold text-zinc-200">선택된 실험</h3>
              </div>
              <span v-if="selectedRecentRun" :class="['badge shrink-0', statusClass(selectedRecentRun.status)]">
                {{ getStatusLabel(selectedRecentRun.status) }}
              </span>
            </div>
            <template v-if="selectedRecentRunSummary">
              <p class="truncate text-base font-semibold text-zinc-100">{{ selectedRecentRunSummary.run.name }}</p>
              <p class="mt-1 text-xs text-zinc-500">
                {{ selectedRecentRunSummary.run.dataset_name }} · {{ getDatasetTypeLabel(selectedRecentRunSummary.run.dataset_type) }} ·
                {{ selectedRecentRunSummary.completedModels }}/{{ selectedRecentRunSummary.totalModels }}개 모델 완료
              </p>
              <div v-if="selectedRecentRun?.status === 'completed'" class="mt-4 grid grid-cols-3 gap-2">
                <div class="subsection-card p-3">
                  <p class="text-[10px] uppercase tracking-widest text-zinc-500">정확도</p>
                  <p class="mt-1 text-sm font-semibold text-zinc-100">{{ formatOptionalPercent(selectedRecentRunSummary.accuracy) }}</p>
                </div>
                <div class="subsection-card p-3">
                  <p class="text-[10px] uppercase tracking-widest text-zinc-500">p95</p>
                  <p class="mt-1 text-sm font-semibold text-zinc-100">{{ formatOptionalMs(selectedRecentRunSummary.latency) }}</p>
                </div>
                <div class="subsection-card p-3">
                  <p class="text-[10px] uppercase tracking-widest text-zinc-500">비용</p>
                  <p class="mt-1 text-sm font-semibold text-zinc-100">{{ formatUsd(selectedRecentRunSummary.cost) }}</p>
                </div>
              </div>
              <p v-else class="mt-3 text-sm text-zinc-500">
                {{
                  selectedRecentRun?.status === 'running'
                    ? '실험이 실행 중입니다. 완료되면 지표가 표시됩니다.'
                    : '아직 완료된 결과가 없습니다.'
                }}
              </p>
              <button
                class="btn-soft-primary mt-4 w-full"
                type="button"
                @click="openWorkspaceTab('model-evaluation')"
              >
                결과 분석 보기
              </button>
            </template>
            <p v-else class="text-sm text-zinc-600">선택할 실험이 없습니다.</p>
          </div>

          <div class="grid gap-2">
            <button class="rounded-lg bg-indigo-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-indigo-500" type="button" @click="openWorkspaceTab('evaluation-runs')">
              새 실험 만들기
            </button>
            <button class="rounded-lg border border-zinc-700 px-4 py-3 text-sm font-semibold text-zinc-300 transition hover:border-indigo-500/50 hover:text-indigo-300" type="button" @click="openWorkspaceTab('model-evaluation')">
              결과 분석 보기
            </button>
            <button class="rounded-lg border border-zinc-700 px-4 py-3 text-sm font-semibold text-zinc-300 transition hover:border-indigo-500/50 hover:text-indigo-300" type="button" @click="openWorkspaceTab('evaluation-methods')">
              평가방식 관리
            </button>
          </div>
        </div>
      </section>

      <section v-if="experimentMetrics" class="space-y-4">
        <div class="rounded-xl border border-zinc-800 bg-zinc-900 p-5">
          <div class="mb-4 flex items-center gap-2">
            <ActivityIcon class="h-4 w-4 text-indigo-400" />
            <div>
              <h3 class="text-sm font-semibold text-zinc-200">실험 현황</h3>
              <p class="mt-1 text-xs text-zinc-500">선택한 기간의 평가 실행 결과와 모델 성능을 요약합니다.</p>
            </div>
          </div>

          <div class="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <div class="subsection-card p-4">
              <p class="text-xs font-medium text-zinc-500">완료 실험</p>
              <p class="mt-1 text-2xl font-bold text-zinc-100">{{ experimentMetrics.runs.completed }}</p>
              <p class="mt-1 text-xs text-zinc-500">전체 {{ experimentMetrics.runs.total }} · 실패 {{ experimentMetrics.runs.failed }}</p>
            </div>
            <div class="subsection-card p-4">
              <p class="text-xs font-medium text-zinc-500">평균 정확도</p>
              <p class="mt-1 text-2xl font-bold text-zinc-100">{{ formatOptionalPercent(experimentMetrics.results.average_accuracy) }}</p>
              <p class="mt-1 text-xs text-zinc-500">완료 결과 {{ experimentMetrics.results.completed_count }}건</p>
            </div>
            <div class="subsection-card p-4">
              <p class="text-xs font-medium text-zinc-500">평균 p95 지연</p>
              <p class="mt-1 text-2xl font-bold text-zinc-100">{{ formatOptionalMs(experimentMetrics.results.average_latency_p95_ms) }}</p>
              <p class="mt-1 text-xs text-zinc-500">실패율 {{ formatOptionalPercent(experimentMetrics.results.average_failure_rate) }}</p>
            </div>
            <div class="subsection-card p-4">
              <p class="text-xs font-medium text-zinc-500">누적 예상 비용</p>
              <p class="mt-1 text-2xl font-bold text-zinc-100">{{ formatUsd(experimentMetrics.results.total_estimated_cost_usd) }}</p>
              <p class="mt-1 text-xs text-zinc-500">완료된 모델 결과 기준</p>
            </div>
          </div>
        </div>

        <div class="grid gap-4 xl:grid-cols-[minmax(0,1fr)_24rem]">
          <div class="rounded-xl border border-zinc-800 bg-zinc-900 p-5">
            <div class="mb-4 flex items-center justify-between gap-3">
              <div class="flex items-center gap-2">
                <BarChart3Icon class="h-4 w-4 text-indigo-400" />
                <h3 class="text-sm font-semibold text-zinc-200">모델별 실험 성능</h3>
              </div>
            </div>
            <div class="space-y-2">
              <div
                v-for="item in experimentMetrics.model_performance"
                :key="`${item.model__provider}-${item.model__name}`"
                class="grid grid-cols-[minmax(0,1fr)_auto] gap-3 rounded-lg bg-zinc-800/50 px-3 py-2.5"
              >
                <div class="min-w-0">
                  <p class="truncate text-sm font-medium text-zinc-300">{{ item.model__display_name || item.model__name }}</p>
                  <p class="text-xs text-zinc-500">{{ item.model__provider }}/{{ item.model__name }} · {{ item.result_count }}회 평가</p>
                </div>
                <div class="text-right">
                  <p class="text-sm font-semibold text-zinc-100">{{ formatOptionalPercent(item.average_accuracy) }}</p>
                  <p class="text-xs text-zinc-500">p95 {{ formatOptionalMs(item.average_latency_p95_ms) }}</p>
                </div>
              </div>
              <p v-if="!experimentMetrics.model_performance.length" class="text-sm text-zinc-600">선택 기간에 완료된 모델 결과가 없습니다.</p>
            </div>
          </div>

          <div class="space-y-4">
            <div class="rounded-xl border border-zinc-800 bg-zinc-900 p-5">
              <div class="mb-3 flex items-center gap-2">
                <ServerIcon class="h-4 w-4 text-amber-400" />
                <h3 class="text-sm font-semibold text-zinc-200">Ollama 연결 상태</h3>
              </div>
              <div class="flex items-start gap-2">
                <component
                  :is="experimentMetrics.ollama_status.reachable ? CheckCircle2Icon : XCircleIcon"
                  :class="[
                    'mt-0.5 h-4 w-4 shrink-0',
                    experimentMetrics.ollama_status.reachable ? 'text-emerald-400' : 'text-red-400'
                  ]"
                />
                <div class="min-w-0">
                  <p :class="['text-sm font-semibold', experimentMetrics.ollama_status.reachable ? 'text-emerald-300' : 'text-red-300']">
                    {{ experimentMetrics.ollama_status.reachable ? '로컬 Ollama 서버 연결됨' : '로컬 Ollama 서버에 연결되지 않음' }}
                  </p>
                  <p class="mt-1 text-xs text-zinc-500">{{ experimentMetrics.ollama_status.base_url }}</p>
                  <p class="mt-1 text-xs text-zinc-600">{{ experimentMetrics.ollama_status.message }}</p>
                </div>
              </div>
              <div class="mt-4 space-y-2">
                <div
                  v-for="model in experimentMetrics.ollama_status.registered_models"
                  :key="model.model_id"
                  class="flex items-center justify-between rounded-lg bg-zinc-800/50 px-3 py-2"
                >
                  <div class="min-w-0">
                    <p class="truncate text-sm text-zinc-300">{{ model.display_name || model.model }}</p>
                    <p class="text-xs text-zinc-500">{{ model.model }}</p>
                  </div>
                  <span :class="['badge shrink-0', connectivityStatusClass(model.status)]">{{ connectivityStatusLabel(model.status) }}</span>
                </div>
                <p v-if="!experimentMetrics.ollama_status.registered_models.length" class="text-sm text-zinc-600">등록된 Ollama 모델이 없습니다.</p>
              </div>
            </div>

            <div class="rounded-xl border border-zinc-800 bg-zinc-900 p-5">
              <div class="mb-3 flex items-center justify-between gap-2">
                <div class="flex items-center gap-2">
                  <CpuIcon class="h-4 w-4 text-indigo-400" />
                  <h3 class="text-sm font-semibold text-zinc-200">모델 가용성</h3>
                </div>
                <span class="text-xs text-zinc-500">
                  사용 가능 {{ experimentMetrics.connectivity_summary.online }} / 전체 {{ experimentMetrics.model_connectivity.length }}
                </span>
              </div>
              <div class="space-y-2">
                <div
                  v-for="model in experimentMetrics.model_connectivity"
                  :key="model.model_id"
                  class="flex items-center justify-between rounded-lg bg-zinc-800/50 px-3 py-2"
                >
                  <div class="min-w-0">
                    <p class="truncate text-sm text-zinc-300">{{ model.display_name || model.model }}</p>
                    <p class="truncate text-xs text-zinc-500">{{ model.provider }}/{{ model.model }}</p>
                  </div>
                  <span :class="['badge shrink-0', connectivityStatusClass(model.status)]">{{ connectivityStatusLabel(model.status) }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="rounded-xl border border-zinc-800 bg-zinc-900 p-5">
          <h3 class="mb-4 text-sm font-semibold text-zinc-200">기간 내 완료 실험</h3>
          <div class="space-y-2">
            <div
              v-for="run in experimentMetrics.recent_completed_runs"
              :key="run.id"
              class="flex items-center justify-between rounded-lg bg-zinc-800/50 px-3 py-2.5"
            >
              <div class="min-w-0">
                <p class="truncate text-sm font-medium text-zinc-300">{{ run.name }}</p>
                <p class="text-xs text-zinc-500">{{ run.dataset_name }} · {{ run.evaluation_method_name || '평가방식 미지정' }}</p>
              </div>
              <div class="text-right">
                <p class="text-sm font-semibold text-zinc-100">{{ formatOptionalPercent(run.average_accuracy) }}</p>
                <p class="text-xs text-zinc-500">{{ formatDate(run.completed_at) }}</p>
              </div>
            </div>
            <p v-if="!experimentMetrics.recent_completed_runs.length" class="text-sm text-zinc-600">선택 기간에 완료된 실험이 없습니다.</p>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>
