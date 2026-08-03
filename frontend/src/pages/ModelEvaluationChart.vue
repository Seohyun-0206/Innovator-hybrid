<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import {
  BarChart3Icon,
  BeakerIcon,
  CircleGaugeIcon,
  Clock3Icon,
  CoinsIcon,
  DownloadIcon,
  GaugeIcon,
  InfoIcon,
  ListIcon,
  ListChecksIcon,
  RefreshCwIcon,
  RouteIcon,
  SearchIcon,
  ShieldCheckIcon,
  SparklesIcon,
  TargetIcon,
  ZapIcon,
} from 'lucide-vue-next'
import AdminDataTable from '../components/common/AdminDataTable.vue'
import { EvaluationResult, EvaluationRun, useApi } from '../composables/useApi'

type MetricColumn = {
  key: string
  label: string
  description: string
  getValue: (result: EvaluationResult) => string
}

type PerformanceSeriesDefinition = {
  label: string
  color: string
  getValue: (result: EvaluationResult) => number | null
  format: (value: number | null) => string
}

type PerformanceChartDefinition = {
  key: string
  title: string
  description: string
  series: PerformanceSeriesDefinition[]
  fixedMax?: number
}

type CandidateView = {
  result: EvaluationResult
  id: number
  label: string
  kind: 'single_model' | 'routing'
  accuracy: number | null
  failureRate: number | null
  parseFailureRate: number | null
  answerP95: number | null
  routerP95: number | null
  tokens: number
  cost: number | null
}

type RoutingVerdict = {
  candidate: CandidateView
  largeBaseline: CandidateView | null
  smallBaseline: CandidateView | null
  accuracyDelta: number | null
  smallAccuracyDelta: number | null
  latencySaving: number | null
  tokenSaving: number | null
  tone: 'positive' | 'neutral' | 'negative' | 'insufficient'
  title: string
  description: string
}

const api = useApi()
const runs = ref<EvaluationRun[]>([])
const allResults = ref<EvaluationResult[]>([])
const selectedRunId = ref<number | null>(null)
const loading = ref(false)
const errorMessage = ref('')
const viewMode = ref<'chart' | 'table'>('chart')
const modelSearchQuery = ref('')
const runSearchQuery = ref('')
const downloadingItemLogs = ref(false)

const filteredRuns = computed(() => {
  const query = runSearchQuery.value.trim().toLowerCase()
  return [...runs.value]
    .filter((run) =>
      !query ||
      run.name.toLowerCase().includes(query) ||
      run.dataset_name.toLowerCase().includes(query) ||
      run.dataset_type.toLowerCase().includes(query) ||
      (run.evaluation_method_name ?? '').toLowerCase().includes(query) ||
      (run.evaluation_method_type ?? '').toLowerCase().includes(query) ||
      run.status.toLowerCase().includes(query),
    )
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
})

const selectedRun = computed(() =>
  runs.value.find((run) => run.id === selectedRunId.value) ?? filteredRuns.value[0] ?? null,
)

const allRunResults = computed(() => {
  if (!selectedRun.value) return []
  const embedded = selectedRun.value.results ?? []
  return embedded.length
    ? embedded
    : allResults.value.filter((result) => result.run === selectedRun.value?.id)
})

const runResults = computed(() => allRunResults.value.filter((result) => result.status === 'completed'))

const filteredTableResults = computed(() => {
  const query = modelSearchQuery.value.trim().toLowerCase()
  return allRunResults.value.filter((result) =>
    !query ||
    (result.model_display_name ?? '').toLowerCase().includes(query) ||
    (result.model_name ?? '').toLowerCase().includes(query) ||
    (result.model_provider ?? '').toLowerCase().includes(query) ||
    result.candidate_label.toLowerCase().includes(query) ||
    (result.routing_config?.small_model_display_name ?? '').toLowerCase().includes(query) ||
    (result.routing_config?.large_model_display_name ?? '').toLowerCase().includes(query) ||
    result.status.toLowerCase().includes(query),
  )
})

const candidates = computed<CandidateView[]>(() =>
  runResults.value.map((result) => {
    const routerP95 = result.result_type === 'routing' ? finiteNumber(result.router_latency_p95_ms) : null
    const answerP95 = finiteNumber(result.latency_p95_ms)
    return {
      result,
      id: result.id,
      label: result.candidate_label || result.model_display_name || result.model_name || `후보 ${result.id}`,
      kind: result.result_type,
      accuracy: ratioNumber(result.overall_accuracy),
      failureRate: ratioNumber(result.failure_rate),
      parseFailureRate: ratioNumber(result.parse_failure_rate),
      answerP95,
      routerP95,
      tokens: (result.input_tokens || 0) + (result.output_tokens || 0),
      cost: finiteNumber(result.estimated_cost_usd),
    }
  }),
)

const singleCandidates = computed(() => candidates.value.filter((candidate) => candidate.kind === 'single_model'))
const routingCandidates = computed(() => candidates.value.filter((candidate) => candidate.kind === 'routing'))
const excludedResults = computed(() => {
  return allRunResults.value.filter((result) => result.status !== 'completed')
})

const bestAccuracy = computed(() => maxNullable(candidates.value.map((candidate) => candidate.accuracy)))
const fastestLatency = computed(() => minNullable(candidates.value.map((candidate) => candidate.answerP95)))
const lowestTokens = computed(() => minNullable(candidates.value.map((candidate) => candidate.tokens)))

const isMultipleChoiceRun = computed(() => {
  const methodType = (selectedRun.value?.evaluation_method_type ?? '').toLowerCase()
  const methodName = (selectedRun.value?.evaluation_method_name ?? '').toLowerCase()
  const datasetType = (selectedRun.value?.dataset_type ?? '').toLowerCase()
  return methodType.includes('multiple_choice') || methodName.includes('mmlu') || datasetType === 'mmlu' || datasetType === 'custom_mcq'
})

const scorecardMetricKeys = computed(() => {
  const keys = new Set<string>()
  allRunResults.value.forEach((result) => {
    Object.entries(result.scorecard ?? {}).forEach(([key, value]) => {
      if (key !== 'recommended_role' && (typeof value === 'number' || typeof value === 'string')) keys.add(key)
    })
  })
  return [...keys].slice(0, 4)
})

const hasScorecardMetrics = computed(() => scorecardMetricKeys.value.length > 0)
const hasRoutingResults = computed(() => allRunResults.value.some((result) => result.result_type === 'routing'))

const metricColumns = computed<MetricColumn[]>(() => {
  const columns: MetricColumn[] = [
    { key: 'accuracy', label: '정확도', description: '전체 문항 중 정답으로 판정된 비율입니다.', getValue: (result) => formatRatio(result.overall_accuracy) },
    { key: 'latency', label: '지연 p50/p95', description: '요청부터 응답 완료까지 걸린 시간의 p50/p95입니다.', getValue: (result) => `${formatMs(result.latency_p50_ms)} / ${formatMs(result.latency_p95_ms)}` },
    { key: 'tokens', label: '토큰/비용', description: '입력·출력 토큰 합계와 추정 비용입니다.', getValue: (result) => `${tokens((result.input_tokens || 0) + (result.output_tokens || 0))} tok · ${formatCost(finiteNumber(result.estimated_cost_usd))}` },
    { key: 'failure', label: '실패율', description: '전체 평가 시도 중 실패한 비율입니다.', getValue: (result) => formatRatio(result.failure_rate) },
    { key: 'ttft', label: 'TTFT p50/p95', description: '첫 토큰을 받기까지 걸린 시간의 p50/p95입니다.', getValue: (result) => `${formatMs(result.ttft_p50_ms)} / ${formatMs(result.ttft_p95_ms)}` },
    { key: 'tpot', label: 'TPOT p50/p95', description: '토큰 하나를 생성하는 데 걸린 시간의 p50/p95입니다.', getValue: (result) => `${formatDecimalMs(result.tpot_p50_ms)} / ${formatDecimalMs(result.tpot_p95_ms)}` },
    { key: 'throughput', label: 'Throughput p50/p95', description: '개별 요청의 초당 생성 토큰 수 p50/p95입니다.', getValue: (result) => `${formatTps(result.throughput_p50_tps)} / ${formatTps(result.throughput_p95_tps)}` },
    { key: 'system-throughput', label: 'System Throughput', description: '전체 실험 구간의 초당 출력 토큰 수입니다.', getValue: (result) => formatTps(result.system_throughput_tps) },
    { key: 'kv-cache', label: 'KV Cache 사용률', description: '평균 GPU KV 캐시 사용률입니다.', getValue: (result) => formatKvCache(result.kv_cache_usage_avg) },
  ]
  if (isMultipleChoiceRun.value) {
    columns.splice(1, 0, { key: 'strict', label: 'Strict', description: '요구한 선택지 형식을 정확히 지킨 비율입니다.', getValue: (result) => formatRatio(result.strict_compliance_rate) })
    columns.splice(2, 0, { key: 'parse-failure', label: 'Parse 실패', description: '유효한 선택지를 추출하지 못한 비율입니다.', getValue: (result) => formatRatio(result.parse_failure_rate) })
  }
  scorecardMetricKeys.value.forEach((key) => columns.push({
    key: `scorecard-${key}`,
    label: formatMetricLabel(key),
    description: `Scorecard의 ${formatMetricLabel(key)} 지표입니다.`,
    getValue: (result) => formatUnknownMetric(result.scorecard?.[key]),
  }))
  return columns
})

const averageAccuracy = computed(() => average(runResults.value.map((result) => finiteNumber(result.overall_accuracy)).filter(isFiniteNumber)))
const averageP95Latency = computed(() => average(runResults.value.map((result) => result.latency_p95_ms).filter(isFiniteNumber)))
const averageFailureRate = computed(() => average(allRunResults.value.map((result) => finiteNumber(result.failure_rate)).filter(isFiniteNumber)))
const totalTokens = computed(() => allRunResults.value.reduce((sum, result) => sum + (result.input_tokens || 0) + (result.output_tokens || 0), 0))
const totalCost = computed(() => allRunResults.value.reduce((sum, result) => sum + Number(result.estimated_cost_usd ?? 0), 0))
const fastestResult = computed(() => [...runResults.value].filter((result) => result.latency_p95_ms !== null).sort((a, b) => (a.latency_p95_ms ?? Infinity) - (b.latency_p95_ms ?? Infinity))[0])
const mostAccurateResult = computed(() => [...runResults.value].filter((result) => result.overall_accuracy !== null).sort((a, b) => Number(b.overall_accuracy) - Number(a.overall_accuracy))[0])
const mostReliableResult = computed(() => [...allRunResults.value].filter((result) => result.failure_rate !== null).sort((a, b) => Number(a.failure_rate) - Number(b.failure_rate))[0])
const categoryHighlights = computed(() => collectAccuracyHighlights('category_accuracy'))
const subjectHighlights = computed(() => collectAccuracyHighlights('subject_accuracy'))

const overviewCards = computed(() => [
  { label: '완료 모델', value: `${runResults.value.length}/${allRunResults.value.length}`, sub: selectedRun.value?.name ?? '-', icon: BarChart3Icon },
  { label: '평균 정확도', value: averageAccuracy.value === null ? '-' : formatRatio(averageAccuracy.value), sub: isMultipleChoiceRun.value ? '정답 기반 metric' : '제공될 때만 계산', icon: ShieldCheckIcon },
  { label: '평균 p95 지연', value: averageP95Latency.value === null ? '-' : formatMs(Math.round(averageP95Latency.value)), sub: '완료 결과 p95 평균', icon: GaugeIcon },
  { label: '토큰 / 비용', value: `${tokens(totalTokens.value)} tok`, sub: `$${totalCost.value.toFixed(6)}`, icon: CoinsIcon },
])

const methodDescription = computed(() => {
  if (isMultipleChoiceRun.value) return {
    title: '객관식/MMLU 계열 분석',
    body: '정확도, Strict 준수율, Parse 실패율, Category/Subject 정확도를 우선 확인합니다. 문항별 로그에서 선택지와 원문 응답을 검증할 수 있습니다.',
  }
  return {
    title: '생성형/커스텀 평가 분석',
    body: '공통 metric, 지연 시간, 토큰, 비용, 실패율을 중심으로 비교합니다. Scorecard가 없는 평가방식은 관측 가능한 지표만 표시합니다.',
  }
})

const performanceCharts = computed<PerformanceChartDefinition[]>(() => {
  const charts: PerformanceChartDefinition[] = [
    {
      key: 'quality',
      title: '정확도 · Strict · Parse 실패',
      description: '정확도와 Strict는 높을수록 좋고 Parse 실패는 낮을수록 좋습니다.',
      fixedMax: 100,
      series: [
        { label: '정확도', color: '#34d399', getValue: (result) => ratioNumber(result.overall_accuracy), format: (value) => percent(value) },
        { label: 'Strict', color: '#818cf8', getValue: (result) => ratioNumber(result.strict_compliance_rate), format: (value) => percent(value) },
        { label: 'Parse 실패', color: '#fb7185', getValue: (result) => ratioNumber(result.parse_failure_rate), format: (value) => percent(value) },
      ],
    },
    {
      key: 'latency',
      title: '응답 지연 p50/p95',
      description: '요청부터 응답 완료까지의 시간이며 낮을수록 좋습니다.',
      series: [
        { label: 'p50', color: '#38bdf8', getValue: (result) => finiteNumber(result.latency_p50_ms), format: latency },
        { label: 'p95', color: '#fbbf24', getValue: (result) => finiteNumber(result.latency_p95_ms), format: latency },
      ],
    },
    {
      key: 'ttft',
      title: 'TTFT p50/p95',
      description: '첫 토큰을 받기까지 걸린 시간이며 낮을수록 좋습니다.',
      series: [
        { label: 'p50', color: '#22d3ee', getValue: (result) => finiteNumber(result.ttft_p50_ms), format: latency },
        { label: 'p95', color: '#a78bfa', getValue: (result) => finiteNumber(result.ttft_p95_ms), format: latency },
      ],
    },
    {
      key: 'tpot',
      title: 'TPOT p50/p95',
      description: '출력 토큰 하나를 생성하는 데 걸린 시간이며 낮을수록 좋습니다.',
      series: [
        { label: 'p50', color: '#2dd4bf', getValue: (result) => finiteNumber(result.tpot_p50_ms), format: (value) => value === null ? '-' : `${value.toFixed(1)}ms` },
        { label: 'p95', color: '#f472b6', getValue: (result) => finiteNumber(result.tpot_p95_ms), format: (value) => value === null ? '-' : `${value.toFixed(1)}ms` },
      ],
    },
    {
      key: 'throughput',
      title: 'Throughput p50/p95',
      description: '개별 요청의 초당 생성 토큰 수이며 높을수록 좋습니다.',
      series: [
        { label: 'p50', color: '#4ade80', getValue: (result) => finiteNumber(result.throughput_p50_tps), format: (value) => value === null ? '-' : `${value.toFixed(1)} tok/s` },
        { label: 'p95', color: '#60a5fa', getValue: (result) => finiteNumber(result.throughput_p95_tps), format: (value) => value === null ? '-' : `${value.toFixed(1)} tok/s` },
      ],
    },
    {
      key: 'system-throughput',
      title: 'System Throughput',
      description: '실험 전체 구간의 초당 출력 토큰 수입니다.',
      series: [{ label: 'tok/s', color: '#c084fc', getValue: (result) => finiteNumber(result.system_throughput_tps), format: (value) => value === null ? '-' : `${value.toFixed(1)} tok/s` }],
    },
    {
      key: 'tokens',
      title: '토큰 사용량',
      description: '입력·출력 토큰 합계이며 낮을수록 좋습니다.',
      series: [{ label: '토큰', color: '#38bdf8', getValue: (result) => (result.input_tokens || 0) + (result.output_tokens || 0), format: (value) => value === null ? '-' : `${tokens(value)} tok` }],
    },
    {
      key: 'cost',
      title: '추정 비용',
      description: '후보별 추정 USD 비용이며 낮을수록 좋습니다.',
      series: [{ label: '비용', color: '#f59e0b', getValue: (result) => finiteNumber(result.estimated_cost_usd), format: (value) => value === null ? '-' : `$${value.toFixed(6)}` }],
    },
    {
      key: 'failure',
      title: '실패율',
      description: '전체 평가 시도 중 실패한 비율이며 낮을수록 좋습니다.',
      fixedMax: 100,
      series: [{ label: '실패율', color: '#fb7185', getValue: (result) => ratioNumber(result.failure_rate), format: (value) => percent(value) }],
    },
    {
      key: 'kv-cache',
      title: 'KV Cache 사용률',
      description: '평균 GPU KV Cache 사용률이며 실행 환경과 함께 해석합니다.',
      fixedMax: 100,
      series: [{ label: 'KV Cache', color: '#a78bfa', getValue: (result) => ratioNumber(result.kv_cache_usage_avg), format: (value) => percent(value) }],
    },
    {
      key: 'logs',
      title: '문항별 로그 수',
      description: '후보별로 저장된 문항 실행 로그 개수입니다.',
      series: [{ label: '로그', color: '#94a3b8', getValue: (result) => finiteNumber(result.item_result_count), format: (value) => value === null ? '-' : `${Math.round(value)}개` }],
    },
  ]

  if (hasRoutingResults.value) {
    charts.push({
      key: 'router-latency',
      title: 'Router Latency p50/p95',
      description: '라우팅 결정 자체에 걸린 시간이며 낮을수록 좋습니다.',
      series: [
        { label: 'p50', color: '#22d3ee', getValue: (result) => result.result_type === 'routing' ? finiteNumber(result.router_latency_p50_ms) : null, format: latency },
        { label: 'p95', color: '#f97316', getValue: (result) => result.result_type === 'routing' ? finiteNumber(result.router_latency_p95_ms) : null, format: latency },
      ],
    })
  }

  scorecardMetricKeys.value.forEach((key, index) => charts.push({
    key: `scorecard-${key}`,
    title: `Scorecard · ${formatMetricLabel(key)}`,
    description: '평가방식이 제공한 Scorecard 수치를 모델별로 비교합니다.',
    series: [{
      label: formatMetricLabel(key),
      color: ['#818cf8', '#34d399', '#fbbf24', '#f472b6'][index % 4],
      getValue: (result: EvaluationResult) => finiteNumber(result.scorecard?.[key]),
      format: (value: number | null) => value === null ? '-' : Number.isInteger(value) ? String(value) : value.toFixed(3),
    }],
  }))

  return charts
})

const routingVerdicts = computed<RoutingVerdict[]>(() => {
  return routingCandidates.value.map((candidate) => {
    const largeModelId = candidate.result.routing_config?.large_model
    const smallModelId = candidate.result.routing_config?.small_model
    const largeBaseline = singleCandidates.value.find((item) => item.result.model === largeModelId) ?? null
    const smallBaseline = singleCandidates.value.find((item) => item.result.model === smallModelId) ?? null
    if (!largeBaseline || !smallBaseline) {
      return {
        candidate,
        largeBaseline,
        smallBaseline,
        accuracyDelta: null,
        smallAccuracyDelta: null,
        latencySaving: null,
        tokenSaving: null,
        tone: 'insufficient',
        title: '비교 기준선 부족',
        description: '이 라우팅을 구성하는 Small 및 Large 모델의 단독 결과가 같은 실험에 모두 있어야 효과를 계산할 수 있습니다.',
      }
    }
    const accuracyDelta = deltaPoints(candidate.accuracy, largeBaseline.accuracy)
    const smallAccuracyDelta = deltaPoints(candidate.accuracy, smallBaseline.accuracy)
    const latencySaving = savingPercent(candidate.answerP95, largeBaseline.answerP95)
    const retryEnabled =
      Number(selectedRun.value?.config?.retry ?? 0) > 0 ||
      Number(selectedRun.value?.config?.max_retries ?? 0) > 0
    const tokenSaving = retryEnabled ? null : savingPercent(candidate.tokens, largeBaseline.tokens)
    return {
      candidate,
      largeBaseline,
      smallBaseline,
      accuracyDelta,
      smallAccuracyDelta,
      latencySaving,
      tokenSaving,
      tone: 'neutral',
      title: '기준선 관측 비교',
      description: retryEnabled
        ? '정확도와 답변 모델 지연을 기준선과 비교합니다. 재시도가 허용된 실행이라 토큰 절감 판단은 제공하지 않습니다.'
        : '정확도·답변 모델 지연·토큰 사용량의 관측 차이입니다. 통계적 유의성이나 실제 사용자 체감 지연을 뜻하지 않습니다.',
    }
  })
})

const chartPoints = computed(() => {
  const valid = candidates.value.filter(
    (candidate) => candidate.accuracy !== null && candidate.answerP95 !== null,
  )
  const latencies = valid.map((candidate) => candidate.answerP95 as number)
  const accuracies = valid.map((candidate) => candidate.accuracy as number)
  const minLatency = Math.min(...latencies, 0)
  const latencyRange = Math.max(Math.max(...latencies, 1) - minLatency, 1)
  const minAccuracy = Math.max(0, Math.min(...accuracies, 100) - 8)
  const accuracyRange = Math.max(100 - minAccuracy, 1)
  return valid.map((candidate) => ({
    ...candidate,
    x: 72 + (((candidate.answerP95 as number) - minLatency) / latencyRange) * 650,
    y: 34 + ((100 - (candidate.accuracy as number)) / accuracyRange) * 226,
  }))
})

const hasComparableData = computed(() => chartPoints.value.length > 0)
const datasetSummary = computed(() => {
  if (!selectedRun.value) return ''
  const scorecardCount = candidates.value
    .map((candidate) => finiteNumber(candidate.result.scorecard?.evaluated_questions))
    .find((value) => value !== null)
  const configuredCount = finiteNumber(selectedRun.value.config?.total_questions ?? selectedRun.value.config?.max_questions)
  const count = scorecardCount ?? configuredCount ?? selectedRun.value.dataset_question_count
  return `${selectedRun.value.dataset_name} · ${count ? `${count.toLocaleString()}문항` : '문항 수 미상'} · ${selectedRun.value.evaluation_method_name ?? '평가방식 미지정'}`
})

const experimentConditions = computed(() => {
  const config = selectedRun.value?.config ?? {}
  return [
    { label: '후보 구성', value: `단독 ${singleCandidates.value.length} · 라우팅 ${routingCandidates.value.length}` },
    { label: 'Seed', value: String(config.seed ?? '-') },
    { label: 'Temperature', value: String(config.temperature ?? '-') },
    { label: '최대 출력', value: config.max_tokens === undefined ? '-' : `${config.max_tokens} tokens` },
    { label: '동시 요청', value: String(config.concurrency ?? 1) },
  ]
})

async function loadData() {
  loading.value = true
  errorMessage.value = ''
  try {
    const [runData, resultData] = await Promise.all([api.getEvaluationRuns(), api.getEvaluationResults()])
    runs.value = runData
    allResults.value = resultData
    const storedRunId = Number(sessionStorage.getItem('selected-evaluation-run-id'))
    if (storedRunId && runData.some((run) => run.id === storedRunId)) {
      selectedRunId.value = storedRunId
      sessionStorage.removeItem('selected-evaluation-run-id')
    }
    if (!selectedRunId.value || !runData.some((run) => run.id === selectedRunId.value)) {
      const sorted = [...runData].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
      selectedRunId.value = sorted.find((run) => run.status === 'completed')?.id ?? sorted[0]?.id ?? null
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '분석 데이터를 불러오지 못했습니다.'
  } finally {
    loading.value = false
  }
}

function finiteNumber(value: unknown): number | null {
  if (value === null || value === undefined || value === '') return null
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

function ratioNumber(value: unknown): number | null {
  const parsed = finiteNumber(value)
  return parsed === null ? null : parsed * 100
}

function isFiniteNumber(value: number | null): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

function average(values: number[]): number | null {
  return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null
}

function maxNullable(values: Array<number | null>): number | null {
  const valid = values.filter((value): value is number => value !== null)
  return valid.length ? Math.max(...valid) : null
}

function minNullable(values: Array<number | null>): number | null {
  const valid = values.filter((value): value is number => value !== null)
  return valid.length ? Math.min(...valid) : null
}

function deltaPoints(value: number | null, reference: number | null): number | null {
  return value === null || reference === null ? null : value - reference
}

function savingPercent(value: number | null, reference: number | null): number | null {
  if (value === null || reference === null || reference === 0) return null
  return ((reference - value) / reference) * 100
}

function percent(value: number | null, digits = 1): string {
  return value === null ? '-' : `${value.toFixed(digits)}%`
}

function signedPoints(value: number | null): string {
  if (value === null) return '-'
  return `${value > 0 ? '+' : ''}${value.toFixed(1)}%p`
}

function signedSaving(value: number | null): string {
  if (value === null) return '-'
  return `${value > 0 ? '↓ ' : value < 0 ? '↑ ' : ''}${Math.abs(value).toFixed(1)}%`
}

function latency(value: number | null): string {
  if (value === null) return '-'
  return value >= 1000 ? `${(value / 1000).toFixed(value >= 10000 ? 1 : 2)}초` : `${Math.round(value)}ms`
}

function tokens(value: number): string {
  return value >= 1000 ? `${(value / 1000).toFixed(1)}K` : value.toLocaleString()
}

function routePercent(candidate: CandidateView, key: 'small' | 'large'): number {
  return Number(candidate.result.routing_model_distribution?.[key]?.percent ?? 0)
}

function hasRoutingDistribution(candidate: CandidateView): boolean {
  const distribution = candidate.result.routing_model_distribution
  const smallCount = finiteNumber(distribution?.small?.count)
  const largeCount = finiteNumber(distribution?.large?.count)
  const smallPercent = finiteNumber(distribution?.small?.percent)
  const largePercent = finiteNumber(distribution?.large?.percent)
  if ([smallCount, largeCount, smallPercent, largePercent].some((value) => value === null || value < 0)) return false
  if ((smallCount as number) + (largeCount as number) <= 0) return false
  if ((smallPercent as number) > 100 || (largePercent as number) > 100) return false
  return Math.abs((smallPercent as number) + (largePercent as number) - 100) <= 0.5
}

function routeCount(candidate: CandidateView, key: 'small' | 'large'): number | null {
  const value = candidate.result.routing_model_distribution?.[key]?.count
  return value === undefined || value === null ? null : Number(value)
}

function routeTotal(candidate: CandidateView): number | null {
  const small = routeCount(candidate, 'small')
  const large = routeCount(candidate, 'large')
  return small === null || large === null ? null : small + large
}

function formatCost(value: number | null): string {
  if (value === null) return '미측정'
  if (value === 0) return '$0 (판단 불가)'
  return `$${value.toFixed(6)}`
}

function formatRatio(value: unknown): string {
  return percent(ratioNumber(value))
}

function formatMs(value: number | null): string {
  return value === null ? '-' : `${value}ms`
}

function formatDecimalMs(value: string | null): string {
  return value === null ? '-' : `${Number(value).toFixed(1)}ms`
}

function formatTps(value: string | null): string {
  return value === null ? '-' : `${Number(value).toFixed(1)} tok/s`
}

function formatKvCache(value: string | null): string {
  return value === null ? '-' : `${(Number(value) * 100).toFixed(1)}%`
}

function formatMetricLabel(key: string): string {
  return key.replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase())
}

function formatUnknownMetric(value: unknown): string {
  if (value === null || value === undefined || value === '') return '-'
  if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(3)
  return typeof value === 'string' ? value : '-'
}

function resultDisplayName(result: EvaluationResult): string {
  return result.result_type === 'routing' ? result.candidate_label : result.model_display_name ?? result.model_name ?? '-'
}

function getStatusLabel(status: string): string {
  if (status === 'pending') return '대기'
  if (status === 'running') return '실행 중'
  if (status === 'completed') return '완료'
  if (status === 'failed') return '실패'
  return status
}

function statusClass(status: string): string {
  if (status === 'completed') return 'badge-success'
  if (status === 'failed') return 'badge-danger'
  if (status === 'running') return 'badge-primary'
  return 'badge-warning'
}

function formatRoutingDistribution(result: EvaluationResult): string {
  if (result.result_type !== 'routing') return '-'
  const small = result.routing_model_distribution?.small
  const large = result.routing_model_distribution?.large
  if (!small && !large) return '-'
  return `Small ${small?.percent ?? 0}% · Large ${large?.percent ?? 0}%`
}

function formatRouterLatency(result: EvaluationResult): string {
  if (result.result_type !== 'routing') return '-'
  if (result.router_latency_p50_ms === null && result.router_latency_p95_ms === null) return '-'
  return `${formatMs(result.router_latency_p50_ms)} / ${formatMs(result.router_latency_p95_ms)}`
}

function getRole(result: EvaluationResult): string {
  const role = result.scorecard?.recommended_role
  if (typeof role === 'string') return role
  const accuracy = Number(result.overall_accuracy ?? 0)
  const failureRate = Number(result.failure_rate ?? 0)
  if (failureRate > 0.25) return 'Escalation Candidate'
  if (accuracy >= 0.8) return 'Accurate Path'
  if ((result.latency_p95_ms ?? Infinity) <= 3000 && (result.overall_accuracy === null || accuracy >= 0.55)) return 'Fast Path'
  return 'Review Needed'
}

function roleClass(role: string): string {
  if (role === 'Accurate Path') return 'badge-primary'
  if (role === 'Fast Path') return 'badge-success'
  if (role === 'Escalation Candidate') return 'badge-warning'
  return 'badge-muted'
}

function csvEscape(value: unknown): string {
  const text = value === null || value === undefined ? '' : String(value)
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text
}

function downloadTableCsv() {
  if (!selectedRun.value) return
  const header = ['모델', '유형', 'Provider', '상태', ...metricColumns.value.map((column) => column.label), ...(hasRoutingResults.value ? ['Routing 분포', 'Router Latency p50/p95'] : []), '문항/로그', ...(hasScorecardMetrics.value ? ['Scorecard 역할'] : [])]
  const rows = filteredTableResults.value.map((result) => [
    resultDisplayName(result), result.result_type === 'routing' ? '라우팅' : '단일 모델', result.result_type === 'routing' ? '-' : result.model_provider, getStatusLabel(result.status),
    ...metricColumns.value.map((column) => column.getValue(result)),
    ...(hasRoutingResults.value ? [formatRoutingDistribution(result), formatRouterLatency(result)] : []),
    result.item_result_count || 0,
    ...(hasScorecardMetrics.value ? [getRole(result)] : []),
  ])
  const csv = [header, ...rows].map((row) => row.map(csvEscape).join(',')).join('\r\n')
  const url = URL.createObjectURL(new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' }))
  const link = document.createElement('a')
  link.href = url
  link.download = `${selectedRun.value.name.replace(/[\\/:*?"<>|]/g, '_')}_전체지표.csv`
  link.click()
  URL.revokeObjectURL(url)
}

async function downloadItemLogsCsv() {
  if (!selectedRun.value) return
  downloadingItemLogs.value = true
  try {
    const items = await api.getEvaluationItemResults({ run: selectedRun.value.id })
    const labels = new Map(allRunResults.value.map((result) => [result.id, resultDisplayName(result)]))
    const header = ['후보', '문항번호', '시도', '문제', '정답', '예측', '정답여부', 'Strict여부', '응답성공여부', '입력토큰', '출력토큰', '지연(ms)', 'TTFT(ms)', 'Router Output', '원문 응답', '에러', 'Subject', 'Category']
    const rows = items.map((item) => [labels.get(item.result) ?? item.model_display_name ?? '-', item.item_index, item.attempt, item.question, item.gold, item.predicted_choice, item.is_correct ? 'Y' : 'N', item.strict_ok ? 'Y' : 'N', item.ok ? 'Y' : 'N', item.input_tokens, item.output_tokens, item.latency_ms ?? '', item.ttft_ms ?? '', item.router_output, item.raw_output, item.error, item.subject, item.category])
    const csv = [header, ...rows].map((row) => row.map(csvEscape).join(',')).join('\r\n')
    const url = URL.createObjectURL(new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' }))
    const link = document.createElement('a')
    link.href = url
    link.download = `${selectedRun.value.name.replace(/[\\/:*?"<>|]/g, '_')}_문항로그.csv`
    link.click()
    URL.revokeObjectURL(url)
  } finally {
    downloadingItemLogs.value = false
  }
}

function collectAccuracyHighlights(field: 'category_accuracy' | 'subject_accuracy') {
  const valuesByName = new Map<string, number[]>()
  runResults.value.forEach((result) => {
    Object.entries(result[field] ?? {}).forEach(([name, value]) => {
      const parsed = finiteNumber(value)
      if (parsed !== null) valuesByName.set(name, [...(valuesByName.get(name) ?? []), parsed])
    })
  })
  return [...valuesByName.entries()]
    .map(([name, values]) => ({ name, value: average(values) ?? 0 }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 5)
}

function performanceChartMax(chart: PerformanceChartDefinition): number {
  if (chart.fixedMax !== undefined) return chart.fixedMax
  return Math.max(...chart.series.flatMap((series) => allRunResults.value.map((result) => Math.abs(series.getValue(result) ?? 0))), 0)
}

function performanceBarHeight(chart: PerformanceChartDefinition, series: PerformanceSeriesDefinition, result: EvaluationResult): string {
  const value = series.getValue(result)
  const max = performanceChartMax(chart)
  if (value === null || max <= 0) return '0%'
  return `${Math.max(2, (Math.abs(value) / max) * 100)}%`
}

watch(filteredRuns, (nextRuns) => {
  if (!nextRuns.length) return
  if (!nextRuns.some((run) => run.id === selectedRunId.value)) selectedRunId.value = nextRuns[0].id
})

watch(selectedRunId, () => {
  modelSearchQuery.value = ''
})

onMounted(loadData)
</script>

<template>
  <div class="page-shell mx-auto max-w-[1600px]">
    <header class="page-header">
      <div>
        <p class="page-label">Experiment decision view</p>
        <h1 class="page-title flex items-center gap-2">
          <BarChart3Icon class="h-6 w-6 text-indigo-400" />
          결과 분석 (Chart)
        </h1>
        <p class="page-subtitle">단독 모델과 라우팅 정책의 품질·속도·사용량 차이를 한눈에 비교합니다.</p>
      </div>
      <div class="flex flex-wrap items-center gap-2">
        <div class="flex rounded-lg border border-zinc-700 bg-zinc-900 p-1" aria-label="결과 보기 방식">
          <button
            :class="['flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-semibold transition', viewMode === 'chart' ? 'bg-indigo-500/20 text-indigo-300' : 'text-zinc-500 hover:text-zinc-200']"
            type="button"
            @click="viewMode = 'chart'"
          >
            <BarChart3Icon class="h-4 w-4" /> 차트
          </button>
          <button
            :class="['flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-semibold transition', viewMode === 'table' ? 'bg-indigo-500/20 text-indigo-300' : 'text-zinc-500 hover:text-zinc-200']"
            type="button"
            @click="viewMode = 'table'"
          >
            <ListIcon class="h-4 w-4" /> 표
          </button>
        </div>
        <button class="btn-secondary" type="button" :disabled="loading" @click="loadData">
          <RefreshCwIcon :class="['h-4 w-4', loading ? 'animate-spin' : '']" />
          새로고침
        </button>
      </div>
    </header>

    <div v-if="errorMessage" class="alert-error mb-5">{{ errorMessage }}</div>

    <section class="section-card mb-3 px-4 py-3">
      <div class="grid gap-3 xl:grid-cols-[minmax(0,1fr)_auto] xl:items-center">
        <div class="grid gap-2 md:grid-cols-[minmax(240px,0.75fr)_minmax(300px,1fr)]">
          <label class="sr-only" for="chart-run-search">실험 검색</label>
          <div class="relative">
            <SearchIcon class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
            <input id="chart-run-search" v-model="runSearchQuery" class="ui-input-search" placeholder="실험 검색..." type="text" />
          </div>
          <select id="chart-run" v-model.number="selectedRunId" class="ui-input" @change="modelSearchQuery = ''">
            <option v-for="run in filteredRuns" :key="run.id" :value="run.id">
              {{ run.name }} · {{ getStatusLabel(run.status) }}
            </option>
          </select>
        </div>
        <p v-if="selectedRun" class="truncate text-xs text-zinc-500" :title="datasetSummary">{{ datasetSummary }}</p>
      </div>
      <p v-if="!filteredRuns.length" class="mt-2 text-xs text-amber-400">검색 조건에 맞는 실험이 없습니다.</p>
    </section>

    <div v-if="loading && !runs.length" class="section-card-padded flex min-h-64 items-center justify-center text-zinc-500">
      <RefreshCwIcon class="mr-2 h-5 w-5 animate-spin" /> 분석 데이터를 불러오는 중입니다.
    </div>

    <div v-else-if="!selectedRun" class="section-card-padded flex min-h-64 flex-col items-center justify-center text-center">
      <BarChart3Icon class="mb-3 h-9 w-9 text-zinc-600" />
      <h2 class="text-base font-semibold text-zinc-200">분석할 완료 실험이 없습니다</h2>
      <p class="mt-1 text-sm text-zinc-500">실험 실행 화면에서 평가를 완료하면 후보 비교 차트가 표시됩니다.</p>
    </div>

    <template v-else>
      <details class="mb-3">
        <summary class="inline-flex cursor-pointer list-none items-center gap-2 rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-xs font-semibold text-zinc-300 transition hover:bg-zinc-800">
          <InfoIcon class="h-3.5 w-3.5 text-indigo-400" /> 상세보기
        </summary>
        <div class="section-card mt-3 p-4">
      <section class="section-card-padded mb-5">
        <div class="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
          <div class="max-w-3xl">
            <p class="text-xs font-semibold uppercase tracking-widest text-indigo-400">실험 개요</p>
            <h2 class="mt-2 text-lg font-semibold text-zinc-100">{{ selectedRun.name }}</h2>
            <p class="mt-2 text-sm leading-6 text-zinc-400">
              {{ selectedRun.notes || '선택한 데이터셋과 평가방식으로 후보들의 품질과 실행 성능을 비교한 실험입니다.' }}
            </p>
            <div class="mt-3 flex flex-wrap gap-2 text-xs">
              <span class="rounded-md border border-zinc-700 bg-zinc-950/50 px-2.5 py-1.5 text-zinc-300">{{ selectedRun.dataset_name }}</span>
              <span class="rounded-md border border-zinc-700 bg-zinc-950/50 px-2.5 py-1.5 text-zinc-300">{{ selectedRun.evaluation_method_name ?? '평가방식 미지정' }}</span>
              <span class="rounded-md border border-zinc-700 bg-zinc-950/50 px-2.5 py-1.5 text-zinc-300">{{ selectedRun.status }}</span>
            </div>
          </div>
          <dl class="grid shrink-0 grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-3 xl:grid-cols-5">
            <div v-for="condition in experimentConditions" :key="condition.label">
              <dt class="text-[11px] font-medium text-zinc-500">{{ condition.label }}</dt>
              <dd class="mt-1 whitespace-nowrap text-sm font-semibold text-zinc-200">{{ condition.value }}</dd>
            </div>
          </dl>
        </div>
      </section>

      <section class="section-card-padded mb-5">
        <div class="flex items-start gap-3">
          <ListChecksIcon class="mt-0.5 h-5 w-5 shrink-0 text-indigo-400" />
          <div>
            <h2 class="text-sm font-semibold text-zinc-200">{{ methodDescription.title }}</h2>
            <p class="mt-1 text-sm leading-6 text-zinc-500">{{ methodDescription.body }}</p>
          </div>
        </div>
      </section>

      <section class="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <article v-for="card in overviewCards" :key="card.label" class="section-card-padded">
          <div class="flex items-center justify-between">
            <span class="text-xs font-medium text-zinc-500">{{ card.label }}</span>
            <component :is="card.icon" class="h-4 w-4 text-indigo-400" />
          </div>
          <p class="mt-3 text-2xl font-bold text-zinc-100">{{ card.value }}</p>
          <p class="mt-1 truncate text-xs text-zinc-500">{{ card.sub }}</p>
        </article>
      </section>

      <section class="mb-5 grid gap-3 md:grid-cols-3">
        <article class="section-card-padded">
          <p class="text-xs font-medium text-zinc-500">평균 실패율</p>
          <p class="mt-2 text-lg font-semibold text-zinc-100">{{ averageFailureRate === null ? '-' : formatRatio(averageFailureRate) }}</p>
          <p class="mt-1 text-xs text-zinc-500">실행 안의 전체 후보 기준</p>
        </article>
        <article class="section-card-padded">
          <p class="text-xs font-medium text-zinc-500">가장 빠른 모델</p>
          <p class="mt-2 text-lg font-semibold text-zinc-100">{{ fastestResult ? resultDisplayName(fastestResult) : '-' }}</p>
          <p class="mt-1 text-xs text-zinc-500">p95 {{ fastestResult ? formatMs(fastestResult.latency_p95_ms) : '-' }} · 실패 {{ fastestResult ? formatRatio(fastestResult.failure_rate) : '-' }}</p>
        </article>
        <article class="section-card-padded">
          <p class="text-xs font-medium text-zinc-500">가장 안정적인 모델</p>
          <p class="mt-2 text-lg font-semibold text-zinc-100">{{ mostReliableResult ? resultDisplayName(mostReliableResult) : '-' }}</p>
          <p class="mt-1 text-xs text-zinc-500">실패 {{ mostReliableResult ? formatRatio(mostReliableResult.failure_rate) : '-' }} · 정확도 {{ mostReliableResult ? formatRatio(mostReliableResult.overall_accuracy) : '-' }}</p>
        </article>
      </section>

      <section v-if="isMultipleChoiceRun" class="mb-5 grid gap-4 lg:grid-cols-2">
        <article class="section-card-padded">
          <h2 class="text-sm font-semibold text-zinc-200">Category 정확도 상위</h2>
          <div class="mt-3 space-y-2">
            <div v-for="item in categoryHighlights" :key="item.name" class="flex items-center justify-between rounded-lg bg-zinc-950/50 px-3 py-2 text-sm">
              <span class="truncate text-zinc-300">{{ item.name }}</span><strong class="text-zinc-200">{{ formatRatio(item.value) }}</strong>
            </div>
            <p v-if="!categoryHighlights.length" class="text-sm text-zinc-600">Category 정확도 데이터가 없습니다.</p>
          </div>
        </article>
        <article class="section-card-padded">
          <h2 class="text-sm font-semibold text-zinc-200">Subject 정확도 상위</h2>
          <div class="mt-3 space-y-2">
            <div v-for="item in subjectHighlights" :key="item.name" class="flex items-center justify-between rounded-lg bg-zinc-950/50 px-3 py-2 text-sm">
              <span class="truncate text-zinc-300">{{ item.name }}</span><strong class="text-zinc-200">{{ formatRatio(item.value) }}</strong>
            </div>
            <p v-if="!subjectHighlights.length" class="text-sm text-zinc-600">Subject 정확도 데이터가 없습니다.</p>
          </div>
        </article>
      </section>

      <details v-if="routingCandidates.length" class="section-card-padded mb-5">
        <summary class="flex cursor-pointer list-none items-center gap-2 text-sm font-semibold text-zinc-200"><RouteIcon class="h-4 w-4 text-violet-400" /> 라우팅 구성과 프롬프트 보기</summary>
        <div class="mt-4 grid gap-4 xl:grid-cols-2">
          <article v-for="candidate in routingCandidates" :key="candidate.id" class="rounded-lg border border-zinc-800 bg-zinc-950/40 p-4">
            <p class="font-semibold text-zinc-200">{{ candidate.label }}</p>
            <p class="mt-1 text-xs text-zinc-500">Small: {{ candidate.result.routing_config?.small_model_display_name ?? '-' }} · Large: {{ candidate.result.routing_config?.large_model_display_name ?? '-' }}</p>
            <pre class="code-panel mt-3 max-h-52 overflow-y-auto whitespace-pre-wrap rounded p-3 text-xs">{{ candidate.result.routing_config?.routing_prompt || '라우팅 프롬프트가 없습니다.' }}</pre>
          </article>
        </div>
      </details>

      <details class="section-card-padded mb-5 border-indigo-500/20 bg-indigo-500/[0.06]">
        <summary class="flex cursor-pointer list-none items-center gap-2 text-sm font-semibold text-indigo-300"><InfoIcon class="h-4 w-4" /> 정책 설계 보조 정보 보기</summary>
        <div class="mt-4 grid gap-4 md:grid-cols-3">
          <div class="rounded-lg border border-indigo-500/20 bg-zinc-950/30 p-4">
            <p class="text-xs font-semibold uppercase tracking-widest text-indigo-300">Fast Path 참고</p>
            <p class="mt-2 text-sm font-semibold text-zinc-100">{{ fastestResult ? resultDisplayName(fastestResult) : '-' }}</p>
            <p class="mt-1 text-xs text-zinc-500">완료 후보 중 p95 지연이 가장 낮은 후보입니다.</p>
          </div>
          <div class="rounded-lg border border-indigo-500/20 bg-zinc-950/30 p-4">
            <p class="text-xs font-semibold uppercase tracking-widest text-indigo-300">Accurate Path 참고</p>
            <p class="mt-2 text-sm font-semibold text-zinc-100">{{ mostAccurateResult ? resultDisplayName(mostAccurateResult) : '-' }}</p>
            <p class="mt-1 text-xs text-zinc-500">완료 후보 중 정확도가 가장 높은 후보입니다.</p>
          </div>
          <div class="rounded-lg border border-indigo-500/20 bg-zinc-950/30 p-4">
            <p class="text-xs font-semibold uppercase tracking-widest text-indigo-300">Escalation 참고</p>
            <p class="mt-2 text-sm font-semibold text-zinc-100">{{ allRunResults.filter((result) => getRole(result) === 'Escalation Candidate').length }}개 후보</p>
            <p class="mt-1 text-xs text-zinc-500">Scorecard 또는 실패율 규칙상 추가 검토 후보입니다.</p>
          </div>
        </div>
      </details>
        </div>
      </details>

      <div class="mb-3 flex flex-wrap justify-end gap-2">
        <button class="btn-secondary" type="button" :disabled="!allRunResults.length" @click="downloadTableCsv">
          <DownloadIcon class="h-4 w-4" /> 결과 요약 CSV
        </button>
        <button class="btn-secondary" type="button" :disabled="!allRunResults.length || downloadingItemLogs" @click="downloadItemLogsCsv">
          <DownloadIcon class="h-4 w-4" /> {{ downloadingItemLogs ? '내려받는 중...' : '문항별 로그 CSV' }}
        </button>
      </div>

      <template v-if="viewMode === 'chart'">
      <section v-if="routingCandidates.length && !singleCandidates.length" class="alert-warning mb-5">
        라우팅 결과는 있지만 비교할 단독 모델 기준선이 없습니다. 같은 데이터셋으로 Large 단독 후보를 함께 평가하세요.
      </section>

      <section v-if="candidates.length" class="mb-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        <article class="section-card px-3 py-2.5">
          <div class="flex items-center justify-between">
            <span class="text-xs font-medium text-zinc-500">평가 후보</span>
            <TargetIcon class="h-4 w-4 text-indigo-400" />
          </div>
          <p class="mt-1 text-lg font-bold text-zinc-100">{{ candidates.length }}개</p>
          <p class="mt-1 text-xs text-zinc-500">단독 {{ singleCandidates.length }} · 라우팅 {{ routingCandidates.length }}</p>
        </article>
        <article class="section-card px-3 py-2.5">
          <div class="flex items-center justify-between">
            <span class="text-xs font-medium text-zinc-500">최고 정확도</span>
            <SparklesIcon class="h-4 w-4 text-emerald-400" />
          </div>
          <p class="mt-1 text-lg font-bold text-zinc-100">{{ percent(bestAccuracy) }}</p>
          <p class="mt-1 truncate text-xs text-zinc-500">{{ candidates.find((item) => item.accuracy === bestAccuracy)?.label ?? '-' }}</p>
        </article>
        <article class="section-card px-3 py-2.5">
          <div class="flex items-center justify-between">
            <span class="flex items-center gap-1 text-xs font-medium text-zinc-500">최저 답변 모델 p95 <InfoIcon class="h-3 w-3" /></span>
            <ZapIcon class="h-4 w-4 text-amber-400" />
          </div>
          <p class="mt-1 text-lg font-bold text-zinc-100">{{ latency(fastestLatency) }}</p>
          <p class="mt-1 truncate text-xs text-zinc-500">{{ candidates.find((item) => item.answerP95 === fastestLatency)?.label ?? '-' }} · 라우터 제외</p>
        </article>
        <article class="section-card px-3 py-2.5">
          <div class="flex items-center justify-between">
            <span class="text-xs font-medium text-zinc-500">최저 토큰 사용</span>
            <CircleGaugeIcon class="h-4 w-4 text-sky-400" />
          </div>
          <p class="mt-1 text-lg font-bold text-zinc-100">{{ lowestTokens === null ? '-' : tokens(lowestTokens) }}</p>
          <p class="mt-1 text-xs text-zinc-500">입력 + 출력 토큰</p>
        </article>
      </section>

      <section v-if="excludedResults.length" class="alert-warning mb-5">
        완료되지 않은 후보 {{ excludedResults.length }}개는 측정값처럼 보이지 않도록 차트에서 제외했습니다:
        {{ excludedResults.map((result) => result.candidate_label || result.model_display_name || `후보 ${result.id}`).join(', ') }}
      </section>

      <section v-if="routingVerdicts.length" class="mb-5 grid gap-4 xl:grid-cols-2">
        <article
          v-for="verdict in routingVerdicts"
          :key="verdict.candidate.id"
          :class="[
            'rounded-xl border p-5',
            verdict.tone === 'positive'
              ? 'border-emerald-500/25 bg-emerald-500/[0.06]'
              : verdict.tone === 'negative'
                ? 'border-red-500/25 bg-red-500/[0.06]'
                : 'border-zinc-800 bg-zinc-900',
          ]"
        >
          <div class="flex items-start justify-between gap-3">
            <div>
              <span class="badge badge-primary">라우팅 관측 비교</span>
              <h2 class="mt-3 font-semibold text-zinc-100">{{ verdict.candidate.label }}</h2>
            </div>
            <InfoIcon class="h-6 w-6 text-zinc-500" />
          </div>
          <p class="mt-4 text-lg font-bold text-zinc-100">{{ verdict.title }}</p>
          <p class="mt-1 text-sm leading-6 text-zinc-400">{{ verdict.description }}</p>
          <div class="mt-4 grid grid-cols-2 gap-3 border-t border-zinc-800/80 pt-4 sm:grid-cols-4">
            <div>
              <p class="text-[11px] text-zinc-500">정확도 vs Large</p>
              <p class="mt-1 text-sm font-semibold text-zinc-200">{{ signedPoints(verdict.accuracyDelta) }}</p>
            </div>
            <div>
              <p class="text-[11px] text-zinc-500">답변 p95 vs Large</p>
              <p class="mt-1 text-sm font-semibold text-zinc-200">{{ signedSaving(verdict.latencySaving) }}</p>
              <p class="mt-0.5 text-[10px] text-zinc-600">라우터 제외</p>
            </div>
            <div>
              <p class="text-[11px] text-zinc-500">정확도 vs Small</p>
              <p class="mt-1 text-sm font-semibold text-zinc-200">{{ signedPoints(verdict.smallAccuracyDelta) }}</p>
            </div>
            <div>
              <p class="text-[11px] text-zinc-500">토큰 vs Large</p>
              <p class="mt-1 text-sm font-semibold text-zinc-200">{{ signedSaving(verdict.tokenSaving) }}</p>
              <p v-if="verdict.tokenSaving === null" class="mt-0.5 text-[10px] text-zinc-600">재시도 또는 기준값 확인 필요</p>
            </div>
          </div>
          <p class="mt-3 text-[11px] text-zinc-600">
            Large 기준: {{ verdict.largeBaseline?.label ?? '없음' }} · Small 기준: {{ verdict.smallBaseline?.label ?? '없음' }}
          </p>
        </article>
      </section>

      <section class="mb-5 grid gap-5 2xl:grid-cols-[1.25fr_0.75fr]">
        <article class="section-card overflow-hidden">
          <div class="border-b border-zinc-800 px-5 py-4">
            <h2 class="flex items-center gap-2 font-semibold text-zinc-100">
              <TargetIcon class="h-4 w-4 text-indigo-400" /> 정확도–지연 트레이드오프
            </h2>
            <p class="mt-1 text-xs text-zinc-500">왼쪽 위에 가까울수록 빠르면서 정확합니다. 점에 마우스를 올리면 수치를 볼 수 있습니다.</p>
          </div>
          <div v-if="hasComparableData" class="p-3 sm:p-5">
            <div class="mb-2 flex flex-wrap gap-4 px-2 text-xs text-zinc-500">
              <span class="flex items-center gap-1.5"><i class="h-2.5 w-2.5 rounded-full bg-sky-400"></i> 단독 모델</span>
              <span class="flex items-center gap-1.5"><i class="h-2.5 w-2.5 rounded-full bg-violet-400"></i> 라우팅</span>
              <span class="ml-auto flex items-center gap-1"><InfoIcon class="h-3 w-3" /> 답변 모델 p95만 비교 · 라우터 지연 제외</span>
            </div>
            <svg class="h-auto w-full" viewBox="0 0 780 310" role="img" aria-label="후보별 정확도와 답변 모델 p95 산점도">
              <line x1="72" y1="20" x2="72" y2="260" stroke="#3f3f46" />
              <line x1="72" y1="260" x2="740" y2="260" stroke="#3f3f46" />
              <line v-for="y in [60, 110, 160, 210]" :key="y" x1="72" :y1="y" x2="740" :y2="y" stroke="#27272a" stroke-dasharray="4 5" />
              <text x="20" y="28" fill="#71717a" font-size="11">정확도</text>
              <text x="600" y="295" fill="#71717a" font-size="11">답변 모델 p95 (라우터 제외) →</text>
              <text x="50" y="38" fill="#71717a" font-size="10">높음</text>
              <text x="46" y="260" fill="#71717a" font-size="10">낮음</text>
              <g v-for="point in chartPoints" :key="point.id" class="cursor-help" tabindex="0">
                <title>{{ point.label }} · 정확도 {{ percent(point.accuracy) }} · 답변 모델 p95 {{ latency(point.answerP95) }} · 라우터 제외</title>
                <circle
                  v-if="point.kind === 'single_model'"
                  :cx="point.x"
                  :cy="point.y"
                  r="11"
                  fill="#38bdf8"
                  fill-opacity="0.18"
                />
                <circle
                  v-if="point.kind === 'single_model'"
                  :cx="point.x"
                  :cy="point.y"
                  r="6"
                  fill="#38bdf8"
                />
                <rect
                  v-else
                  :x="point.x - 7"
                  :y="point.y - 7"
                  width="14"
                  height="14"
                  rx="2"
                  fill="#a78bfa"
                  :transform="`rotate(45 ${point.x} ${point.y})`"
                />
                <text :x="point.x + 10" :y="point.y - 9" fill="#d4d4d8" font-size="10">{{ point.label.slice(0, 22) }}</text>
              </g>
            </svg>
          </div>
          <div v-else class="flex min-h-72 items-center justify-center text-sm text-zinc-500">차트를 그릴 정확도와 지연 데이터가 없습니다.</div>
        </article>

        <article class="section-card overflow-hidden">
          <div class="border-b border-zinc-800 px-5 py-4">
            <h2 class="flex items-center gap-2 font-semibold text-zinc-100">
              <RouteIcon class="h-4 w-4 text-violet-400" /> 라우팅 배분
            </h2>
            <p class="mt-1 text-xs text-zinc-500">라우터가 Small/Large로 분류한 요청 비율입니다.</p>
          </div>
          <div v-if="routingCandidates.length" class="divide-y divide-zinc-800">
            <div v-for="candidate in routingCandidates" :key="candidate.id" class="p-5">
              <p class="truncate text-sm font-semibold text-zinc-200">{{ candidate.label }}</p>
              <div v-if="hasRoutingDistribution(candidate)" class="mt-4 flex items-center gap-5">
                <div
                  class="relative h-24 w-24 shrink-0 rounded-full"
                  :style="{ background: `conic-gradient(#38bdf8 0 ${routePercent(candidate, 'small')}%, #a78bfa ${routePercent(candidate, 'small')}% 100%)` }"
                >
                  <div class="absolute inset-[12px] flex items-center justify-center rounded-full bg-zinc-900 text-xs font-semibold text-zinc-300">
                    {{ routeTotal(candidate) }}건
                  </div>
                </div>
                <div class="min-w-0 flex-1 space-y-3">
                  <div>
                    <div class="flex justify-between text-xs"><span class="text-sky-300">Small</span><strong class="text-zinc-200">{{ routeCount(candidate, 'small') }}건 · {{ percent(routePercent(candidate, 'small'), 0) }}</strong></div>
                    <p class="mt-0.5 truncate text-[11px] text-zinc-600">{{ candidate.result.routing_config?.small_model_display_name ?? '-' }}</p>
                  </div>
                  <div>
                    <div class="flex justify-between text-xs"><span class="text-violet-300">Large</span><strong class="text-zinc-200">{{ routeCount(candidate, 'large') }}건 · {{ percent(routePercent(candidate, 'large'), 0) }}</strong></div>
                    <p class="mt-0.5 truncate text-[11px] text-zinc-600">{{ candidate.result.routing_config?.large_model_display_name ?? '-' }}</p>
                  </div>
                </div>
              </div>
              <p v-else class="mt-4 rounded-lg border border-zinc-800 bg-zinc-950/50 px-3 py-4 text-xs text-zinc-500">라우팅 배분 데이터가 없습니다.</p>
              <p class="mt-3 text-[11px] leading-5 text-amber-300/80">Small에는 유효하지 않거나 비어 있는 라우터 응답이 포함될 수 있습니다. 이 비율만으로 난이도 분류 정확도를 판단할 수 없습니다.</p>
              <div class="mt-4 flex items-center justify-between rounded-lg bg-zinc-950/60 px-3 py-2 text-xs">
                <span class="flex items-center gap-1.5 text-zinc-500"><Clock3Icon class="h-3.5 w-3.5" /> Router p95</span>
                <strong class="text-zinc-300">{{ latency(candidate.routerP95) }}</strong>
              </div>
            </div>
          </div>
          <div v-else class="flex min-h-72 flex-col items-center justify-center px-5 text-center">
            <RouteIcon class="mb-3 h-8 w-8 text-zinc-700" />
            <p class="text-sm font-medium text-zinc-400">라우팅 후보가 없습니다</p>
            <p class="mt-1 text-xs leading-5 text-zinc-600">새 실험에서 Small/Large 라우팅 후보를 추가하면 배분 비율이 표시됩니다.</p>
          </div>
        </article>
      </section>

      <section class="mb-5">
        <div class="mb-4">
          <h2 class="flex items-center gap-2 font-semibold text-zinc-100"><BarChart3Icon class="h-4 w-4 text-indigo-400" /> 모델별 전체 지표 비교</h2>
          <p class="mt-1 text-xs text-zinc-500">X축은 모델, Y축은 실제 측정값입니다. p50·p95처럼 같은 단위의 계열은 동일한 축에서 세로 막대로 직접 비교합니다.</p>
        </div>
        <div v-if="allRunResults.length" class="grid gap-5 xl:grid-cols-2">
          <article
            v-for="chart in performanceCharts"
            :key="chart.key"
            class="section-card overflow-hidden"
            role="img"
            :aria-label="`${chart.title} 후보 비교 막대 차트`"
          >
            <div class="border-b border-zinc-800 px-5 py-4">
              <div class="flex items-start justify-between gap-3">
                <div>
                  <h3 class="text-sm font-semibold text-zinc-100">{{ chart.title }}</h3>
                  <p class="mt-1 text-xs leading-5 text-zinc-500">{{ chart.description }}</p>
                </div>
                <span class="whitespace-nowrap text-[10px] text-zinc-600">축 최대 {{ chart.series[0].format(performanceChartMax(chart)) }}</span>
              </div>
              <div class="mt-3 flex flex-wrap gap-3 text-[11px] text-zinc-500">
                <span v-for="series in chart.series" :key="`${chart.key}-${series.label}`" class="flex items-center gap-1.5">
                  <i class="h-2.5 w-2.5 rounded-sm" :style="{ backgroundColor: series.color }"></i>{{ series.label }}
                </span>
              </div>
            </div>
            <div class="overflow-x-auto p-5">
              <div class="min-w-[420px]" :style="{ minWidth: `${Math.max(420, allRunResults.length * 150)}px` }">
                <div class="relative h-56 border-b border-l border-zinc-700 pl-8">
                  <div class="pointer-events-none absolute inset-0 flex flex-col justify-between">
                    <i v-for="line in 5" :key="`${chart.key}-grid-${line}`" class="block border-t border-zinc-800/80"></i>
                  </div>
                  <span class="absolute left-1 top-1 text-[9px] text-zinc-600">{{ chart.series[0].format(performanceChartMax(chart)) }}</span>
                  <span class="absolute bottom-1 left-1 text-[9px] text-zinc-600">0</span>
                  <div class="relative z-10 flex h-full items-end gap-3 px-2 pt-8">
                    <div v-for="result in allRunResults" :key="`${chart.key}-${result.id}`" class="flex h-full min-w-0 flex-1 items-end justify-center gap-1.5">
                      <div v-for="series in chart.series" :key="`${chart.key}-${result.id}-${series.label}`" class="relative flex h-full min-w-0 flex-1 items-end justify-center">
                        <div
                          class="group relative w-full max-w-12 rounded-t-sm transition-all"
                          :style="{ height: performanceBarHeight(chart, series, result), backgroundColor: series.color }"
                          :title="`${resultDisplayName(result)} · ${series.label} ${series.format(series.getValue(result))}`"
                        >
                          <span class="absolute -top-5 left-1/2 -translate-x-1/2 whitespace-nowrap text-[9px] font-semibold text-zinc-300">{{ series.format(series.getValue(result)) }}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
                <div class="ml-8 flex gap-3 px-2 pt-2">
                  <div v-for="result in allRunResults" :key="`${chart.key}-${result.id}-label`" class="h-10 min-w-0 flex-1 text-center">
                    <p class="truncate text-[10px] font-semibold text-zinc-400" :title="resultDisplayName(result)">{{ resultDisplayName(result) }}</p>
                    <p class="mt-0.5 text-[9px] text-zinc-600">{{ getStatusLabel(result.status) }}</p>
                  </div>
                </div>
              </div>
            </div>
          </article>
        </div>
        <div v-else class="section-card-padded flex min-h-40 items-center justify-center text-sm text-zinc-500">후보 결과가 없습니다.</div>
      </section>
      </template>

      <section v-else class="mb-5">
        <div class="mb-4 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 class="text-base font-semibold text-zinc-100">전체 측정 지표</h2>
            <p class="mt-1 text-xs text-zinc-500">완료·실행 중·대기·실패 후보를 모두 표시합니다. 표는 가로로 스크롤할 수 있습니다.</p>
          </div>
        </div>

        <div class="relative mb-3">
          <SearchIcon class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
          <input v-model="modelSearchQuery" class="ui-input-search" placeholder="모델, Provider, 라우팅 구성, 상태 검색..." type="text" />
        </div>

        <AdminDataTable :loading="loading" :is-empty="filteredTableResults.length === 0">
          <template #head>
            <th class="table-th">모델</th>
            <th class="table-th">유형</th>
            <th class="table-th">Provider</th>
            <th class="table-th">상태</th>
            <th v-for="column in metricColumns" :key="column.key" class="table-th cursor-help" :title="column.description">{{ column.label }}</th>
            <th v-if="hasRoutingResults" class="table-th">Routing 분포</th>
            <th v-if="hasRoutingResults" class="table-th">Router Latency p50/p95</th>
            <th class="table-th">문항/로그</th>
            <th v-if="hasScorecardMetrics" class="table-th">Scorecard 역할</th>
          </template>
          <template #empty>
            <BeakerIcon class="empty-icon" />
            <h3 class="empty-title">표시할 후보 결과가 없습니다</h3>
            <p class="empty-description">검색 조건을 지우거나 다른 실험을 선택하세요.</p>
          </template>
          <tr v-for="result in filteredTableResults" :key="result.id" class="table-row">
            <td class="px-5 py-3.5">
              <p class="whitespace-nowrap font-medium text-zinc-200">{{ resultDisplayName(result) }}</p>
              <p class="whitespace-nowrap text-xs text-zinc-500">
                <template v-if="result.result_type === 'routing'">Small: {{ result.routing_config?.small_model_display_name ?? '-' }} / Large: {{ result.routing_config?.large_model_display_name ?? '-' }}</template>
                <template v-else>{{ result.model_name }}</template>
              </p>
              <p v-if="result.error_message" class="mt-1 max-w-xs truncate text-xs text-red-400" :title="result.error_message">{{ result.error_message }}</p>
            </td>
            <td class="whitespace-nowrap px-5 py-3.5"><span :class="['badge', result.result_type === 'routing' ? 'badge-primary' : 'badge-muted']">{{ result.result_type === 'routing' ? '라우팅' : '단일 모델' }}</span></td>
            <td class="whitespace-nowrap px-5 py-3.5 text-sm capitalize text-zinc-300">{{ result.result_type === 'routing' ? '-' : result.model_provider }}</td>
            <td class="whitespace-nowrap px-5 py-3.5"><span :class="['badge', statusClass(result.status)]">{{ getStatusLabel(result.status) }}</span></td>
            <td v-for="column in metricColumns" :key="`${result.id}-${column.key}`" class="cursor-help whitespace-nowrap px-5 py-3.5 text-sm text-zinc-300" :title="column.description">{{ column.getValue(result) }}</td>
            <td v-if="hasRoutingResults" class="whitespace-nowrap px-5 py-3.5 text-sm text-zinc-300">{{ formatRoutingDistribution(result) }}</td>
            <td v-if="hasRoutingResults" class="whitespace-nowrap px-5 py-3.5 text-sm text-zinc-300">{{ formatRouterLatency(result) }}</td>
            <td class="whitespace-nowrap px-5 py-3.5 text-sm text-zinc-300">{{ result.item_result_count || 0 }}개</td>
            <td v-if="hasScorecardMetrics" class="whitespace-nowrap px-5 py-3.5"><span :class="['badge', roleClass(getRole(result))]">{{ getRole(result) }}</span></td>
          </tr>
        </AdminDataTable>
      </section>

      <footer class="flex items-start gap-2 rounded-lg border border-zinc-800 bg-zinc-950/40 px-4 py-3 text-xs leading-5 text-zinc-500">
        <InfoIcon class="mt-0.5 h-4 w-4 shrink-0" />
        <p>
          모든 증감은 같은 실험 안의 관측값 비교입니다. 답변 모델 p95에는 라우터 시간이 포함되지 않으며, Router p95와 단순 합산해 실제 사용자 체감 p95로 해석할 수 없습니다.
          통계적 유의성이나 최적 정책을 뜻하지 않으므로, 실제 적용 전 충분한 문항 수와 반복 실행으로 재검증해야 합니다.
        </p>
      </footer>
    </template>
  </div>
</template>
