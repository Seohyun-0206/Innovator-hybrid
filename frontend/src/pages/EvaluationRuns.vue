<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import {
  BarChart3Icon,
  BeakerIcon,
  CheckCircle2Icon,
  CircleIcon,
  ClipboardListIcon,
  DatabaseIcon,
  FlaskConicalIcon,
  LayersIcon,
  PlayIcon,
  RefreshCwIcon,
  SearchIcon,
  ServerIcon,
  TrashIcon,
  SettingsIcon,
  SparklesIcon,
} from 'lucide-vue-next'
import AppSelect, { SelectOption } from '../components/common/AppSelect.vue'
import { EvaluationDataset, EvaluationMethod, EvaluationRun, LLMModel, ModelConnectivity, useApi } from '../composables/useApi'

const api = useApi()
const datasets = ref<EvaluationDataset[]>([])
const runs = ref<EvaluationRun[]>([])
const models = ref<LLMModel[]>([])
const methods = ref<EvaluationMethod[]>([])
const loading = ref(false)
const savingRun = ref(false)
const executingRunId = ref<number | null>(null)
const checkingAvailability = ref(false)
const modelConnectivity = ref<ModelConnectivity[]>([])
const searchQuery = ref('')
const statusFilter = ref<'all' | 'pending' | 'running' | 'completed' | 'failed'>('all')
const selectedPreset = ref('custom')
const error = ref('')
const message = ref('')

const runForm = reactive({
  name: '',
  dataset: '',
  evaluation_method: '',
  model_ids: [] as number[],
  few_shot: 0,
  temperature: 0,
  total_questions: 20,
  seed: 42,
  max_tokens: 8,
  timeout_seconds: 120,
  retry: 0,
  notes: '',
})

const datasetTypeOptions: SelectOption[] = [
  { value: 'multiple_choice', label: '객관식 평가' },
  { value: 'qa', label: 'QA' },
  { value: 'generation', label: '생성/요약' },
  { value: 'rag', label: 'RAG' },
  { value: 'safety_classification', label: '안전성/분류' },
  { value: 'custom', label: '기타/사용자 정의' },
  { value: 'mmlu', label: '객관식 평가' },
  { value: 'custom_mcq', label: '객관식 평가' },
  { value: 'jsonl', label: '객관식 평가' },
  { value: 'csv', label: '객관식 평가' },
]

const experimentPresets = [
  {
    id: 'model_compare',
    label: '모델 비교',
    description: '선택한 데이터셋·평가방식으로 여러 모델을 동일 조건(N=48, seed=42)에서 비교합니다.',
    badge: '비교 실험',
    config: { total_questions: 48, seed: 42, few_shot: 0, temperature: 0, max_tokens: 8, timeout_seconds: 120, retry: 0 },
    selectAllModels: true,
  },
  {
    id: 'pilot',
    label: '파일럿 검증',
    description: 'N=20으로 실험 설정과 모델 응답 형식을 빠르게 검증합니다.',
    badge: '빠른 검증',
    config: { total_questions: 20, seed: 42, few_shot: 0, temperature: 0, max_tokens: 8, timeout_seconds: 120, retry: 0 },
  },
  {
    id: 'smoke',
    label: '연결 확인',
    description: 'N=5로 선택 모델의 연결과 기본 응답만 확인합니다.',
    badge: '스모크',
    config: { total_questions: 5, seed: 42, few_shot: 0, temperature: 0, max_tokens: 8, timeout_seconds: 60, retry: 0 },
    selectFirstOnlineModel: true,
  },
  {
    id: 'custom',
    label: '직접 설계',
    description: '데이터셋, 평가방식, 모델, 문항 수를 직접 조합합니다.',
    badge: '자유 설정',
    config: null,
  },
]

const providerLabels: Record<string, string> = {
  ollama: '로컬 Ollama',
  openai: 'OpenAI',
  gemini: 'Gemini',
  openrouter: 'OpenRouter',
  anthropic: 'Anthropic',
}

const datasetOptions = computed<SelectOption[]>(() =>
  datasets.value.map((dataset) => ({
    value: String(dataset.id),
    label: `${dataset.name} (${getDatasetTypeLabel(dataset.dataset_type)})`,
  }))
)

const methodOptions = computed<SelectOption[]>(() =>
  methods.value
    .filter((method) => method.is_active)
    .map((method) => ({
      value: String(method.id),
      label: `${method.display_name} (${method.method_type})`,
    }))
)

const activeModels = computed(() => models.value.filter((model) => model.is_active))

const modelsByProvider = computed(() => {
  const groups: Record<string, LLMModel[]> = {}
  for (const model of activeModels.value) {
    if (!groups[model.provider]) {
      groups[model.provider] = []
    }
    groups[model.provider].push(model)
  }
  return Object.entries(groups).sort(([a], [b]) => a.localeCompare(b))
})

const connectivityByModelId = computed(() =>
  Object.fromEntries(modelConnectivity.value.map((item) => [item.model_id, item]))
)

const selectedDataset = computed(() => datasets.value.find((dataset) => dataset.id === Number(runForm.dataset)) ?? null)
const selectedMethod = computed(() => methods.value.find((method) => method.id === Number(runForm.evaluation_method)) ?? null)
const selectedModels = computed(() => activeModels.value.filter((model) => runForm.model_ids.includes(model.id)))

const selectedOllamaModels = computed(() => selectedModels.value.filter((model) => model.provider === 'ollama'))

const ollamaConnectivityIssue = computed(() => {
  if (!selectedOllamaModels.value.length) return null
  const unavailable = selectedOllamaModels.value
    .map((model) => connectivityByModelId.value[model.id])
    .filter((item) => item && item.status !== 'online')
  return unavailable.length ? unavailable : null
})

const selectedModelsReady = computed(() => {
  if (!runForm.model_ids.length) return false
  return runForm.model_ids.every((modelId) => connectivityByModelId.value[modelId]?.status === 'online')
})

const workflowSteps = computed(() => [
  { id: 'dataset', label: '데이터셋', done: Boolean(runForm.dataset), icon: DatabaseIcon },
  { id: 'method', label: '평가방식', done: Boolean(runForm.evaluation_method), icon: ClipboardListIcon },
  { id: 'models', label: '비교 모델', done: runForm.model_ids.length > 0, icon: LayersIcon },
  { id: 'config', label: '실행 설정', done: runForm.total_questions > 0, icon: SettingsIcon },
])

const readinessChecks = computed(() => [
  { label: '평가 데이터셋 선택', ok: Boolean(runForm.dataset) },
  { label: '평가방식 선택', ok: Boolean(runForm.evaluation_method) },
  { label: '비교 모델 1개 이상', ok: runForm.model_ids.length > 0 },
  { label: '선택 모델 사용 가능', ok: selectedModelsReady.value },
  { label: '평가 문항 수 설정', ok: runForm.total_questions > 0 },
])

const canCreateRun = computed(() => readinessChecks.value.every((check) => check.ok))

const experimentSummaryCards = computed(() => {
  if (!selectedDataset.value || !selectedMethod.value) {
    return []
  }
  return [
    {
      label: '데이터셋',
      value: selectedDataset.value.name,
      sub: `${getDatasetTypeLabel(selectedDataset.value.dataset_type)} · ${selectedDataset.value.question_count || '-'}문항`,
    },
    {
      label: '평가방식',
      value: selectedMethod.value.display_name,
      sub: selectedMethod.value.method_type,
    },
    {
      label: '비교 모델',
      value: `${selectedModels.value.length}개`,
      sub: selectedModels.value.map((model) => model.display_name).join(', ') || '모델을 선택하세요',
    },
    {
      label: '실행 규모',
      value: `N=${runForm.total_questions}`,
      sub: `seed ${runForm.seed} · temp ${runForm.temperature}`,
    },
  ]
})

const filteredRuns = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()
  return runs.value
    .filter((run) => statusFilter.value === 'all' || run.status === statusFilter.value)
    .filter(
      (run) =>
        !query ||
        run.name.toLowerCase().includes(query) ||
        run.dataset_name.toLowerCase().includes(query) ||
        run.dataset_type.toLowerCase().includes(query) ||
        run.status.toLowerCase().includes(query) ||
        (run.evaluation_method_name ?? '').toLowerCase().includes(query)
    )
    .sort((a, b) => new Date(b.updated_at || b.created_at).getTime() - new Date(a.updated_at || a.created_at).getTime())
})

const runStatusCounts = computed(() => ({
  all: runs.value.length,
  pending: runs.value.filter((run) => run.status === 'pending').length,
  running: runs.value.filter((run) => run.status === 'running').length,
  completed: runs.value.filter((run) => run.status === 'completed').length,
  failed: runs.value.filter((run) => run.status === 'failed').length,
}))

async function loadModelAvailability(modelIds?: number[]) {
  checkingAvailability.value = true
  try {
    const availability = await api.getEvaluationModelAvailability({
      modelIds: modelIds?.length ? modelIds : activeModels.value.map((model) => model.id),
    })
    modelConnectivity.value = availability.models
    return availability
  } finally {
    checkingAvailability.value = false
  }
}

async function ensureModelsReady(modelIds: number[]) {
  const availability = await api.getEvaluationModelAvailability({ modelIds })
  modelConnectivity.value = availability.models
  if (!availability.ready) {
    const messages = availability.unavailable_models.map((item) => `${item.provider}/${item.model}: ${item.message}`)
    throw new Error(messages.join('\n'))
  }
  return availability
}

async function ensureModelsReadyForRun(runId: number) {
  const availability = await api.getEvaluationModelAvailability({ runId })
  modelConnectivity.value = availability.models
  if (!availability.ready) {
    const messages = availability.unavailable_models.map((item) => `${item.provider}/${item.model}: ${item.message}`)
    throw new Error(messages.join('\n'))
  }
  return availability
}

async function loadPageData() {
  loading.value = true
  try {
    const [loadedDatasets, loadedRuns, loadedModels, loadedMethods] = await Promise.all([
      api.getEvaluationDatasets(),
      api.getEvaluationRuns(),
      api.getModels(),
      api.getEvaluationMethods(),
    ])
    datasets.value = loadedDatasets
    runs.value = loadedRuns
    models.value = loadedModels
    methods.value = loadedMethods
    if (!runForm.dataset && loadedDatasets[0]) {
      runForm.dataset = String(loadedDatasets[0].id)
    }
    if (!runForm.evaluation_method && loadedMethods[0]) {
      applyMethodDefaults(loadedMethods[0])
    }
    await loadModelAvailability()
  } finally {
    loading.value = false
  }
}

function getDefaultDataset() {
  if (runForm.dataset) {
    return datasets.value.find((dataset) => dataset.id === Number(runForm.dataset)) ?? null
  }
  return datasets.value[0] ?? null
}

function getDefaultMethod() {
  if (runForm.evaluation_method) {
    return methods.value.find((method) => method.id === Number(runForm.evaluation_method)) ?? null
  }
  return methods.value.find((method) => method.is_active) ?? null
}

function getOnlineModelIds() {
  return activeModels.value
    .filter((model) => connectivityByModelId.value[model.id]?.status === 'online')
    .map((model) => model.id)
}

function applyExperimentPreset(presetId: string) {
  selectedPreset.value = presetId
  const preset = experimentPresets.find((item) => item.id === presetId)
  if (!preset) return

  const dataset = getDefaultDataset()
  const method = getDefaultMethod()
  if (dataset) runForm.dataset = String(dataset.id)
  if (method) applyMethodDefaults(method)

  if (presetId === 'model_compare') {
    runForm.model_ids = getOnlineModelIds().length ? getOnlineModelIds() : activeModels.value.map((model) => model.id)
    runForm.name = runForm.name || `${dataset?.name ?? '데이터셋'} 모델 비교`
    runForm.notes = runForm.notes || '동일 조건 모델 비교 실험'
  } else if (presetId === 'pilot') {
    runForm.name = runForm.name || `${dataset?.name ?? '데이터셋'} 파일럿 검증`
  } else if (presetId === 'smoke') {
    const onlineModelId = getOnlineModelIds()[0] ?? activeModels.value[0]?.id
    runForm.model_ids = onlineModelId ? [onlineModelId] : []
    runForm.name = runForm.name || `${dataset?.name ?? '데이터셋'} 연결 확인`
  }

  if (preset.config) {
    Object.assign(runForm, preset.config)
  }
}

async function createRun() {
  error.value = ''
  message.value = ''
  if (!canCreateRun.value) {
    error.value = '실험 설계 체크리스트를 모두 충족한 뒤 생성하세요.'
    return
  }
  savingRun.value = true
  try {
    await ensureModelsReady(runForm.model_ids)
    await api.createEvaluationRun({
      name: runForm.name || `${selectedDatasetName.value} 실험`,
      dataset: Number(runForm.dataset),
      evaluation_method: Number(runForm.evaluation_method),
      model_ids: runForm.model_ids,
      config: {
        few_shot: runForm.few_shot,
        temperature: runForm.temperature,
        total_questions: runForm.total_questions || null,
        max_questions: runForm.total_questions || null,
        seed: runForm.seed,
        max_tokens: runForm.max_tokens,
        timeout_seconds: runForm.timeout_seconds,
        retry: runForm.retry,
      },
      notes: runForm.notes,
    })
    Object.assign(runForm, {
      name: '',
      model_ids: [],
      few_shot: 0,
      temperature: 0,
      total_questions: 20,
      seed: 42,
      max_tokens: 8,
      timeout_seconds: 120,
      retry: 0,
      notes: '',
    })
    selectedPreset.value = 'custom'
    message.value = '실험이 생성되었습니다. 아래 실험 기록에서 실행을 시작하거나 결과 분석으로 이동하세요.'
    await loadPageData()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '실험을 생성하지 못했습니다.'
  } finally {
    savingRun.value = false
  }
}

async function executeRun(run: EvaluationRun) {
  error.value = ''
  message.value = ''
  executingRunId.value = run.id
  try {
    await ensureModelsReadyForRun(run.id)
    await api.executeEvaluationRun(run.id)
    message.value = `"${run.name}" 실험이 완료되었습니다. 결과 분석에서 모델별 정확도와 지연을 확인하세요.`
    await loadPageData()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '실험을 실행하지 못했습니다.'
    await loadPageData()
  } finally {
    executingRunId.value = null
  }
}

async function deleteRun(run: EvaluationRun) {
  if (!confirm(`"${run.name}" 실험을 삭제할까요? 관련 결과와 문항 로그도 함께 삭제됩니다.`)) return
  error.value = ''
  try {
    await api.deleteEvaluationRun(run.id)
    runs.value = runs.value.filter((r) => r.id !== run.id)
  } catch (err) {
    error.value = err instanceof Error ? err.message : '실험을 삭제하지 못했습니다.'
  }
}

function isModelSelected(modelId: number) {
  return runForm.model_ids.includes(modelId)
}

function modelRowClass(modelId: number) {
  return isModelSelected(modelId) ? 'list-item list-item-selected' : 'list-item list-item-hover'
}

function toggleModel(modelId: number) {
  if (runForm.model_ids.includes(modelId)) {
    runForm.model_ids = runForm.model_ids.filter((id) => id !== modelId)
  } else {
    runForm.model_ids = [...runForm.model_ids, modelId]
  }
}

function selectProviderModels(provider: string) {
  const providerModelIds = activeModels.value.filter((model) => model.provider === provider).map((model) => model.id)
  const allSelected = providerModelIds.every((id) => runForm.model_ids.includes(id))
  if (allSelected) {
    runForm.model_ids = runForm.model_ids.filter((id) => !providerModelIds.includes(id))
  } else {
    runForm.model_ids = [...new Set([...runForm.model_ids, ...providerModelIds])]
  }
}

function handleMethodChange(value: string) {
  const method = methods.value.find((item) => item.id === Number(value))
  if (method) {
    applyMethodDefaults(method)
  }
}

function applyMethodDefaults(method: EvaluationMethod) {
  const defaults = method.default_config
  runForm.evaluation_method = String(method.id)
  runForm.few_shot = Number(defaults.few_shot ?? runForm.few_shot)
  runForm.temperature = Number(defaults.temperature ?? runForm.temperature)
  runForm.total_questions = Number(defaults.total_questions ?? defaults.max_questions ?? runForm.total_questions)
  runForm.seed = Number(defaults.seed ?? runForm.seed)
  runForm.max_tokens = Number(defaults.max_tokens ?? runForm.max_tokens)
  runForm.timeout_seconds = Number(defaults.timeout_seconds ?? runForm.timeout_seconds)
  runForm.retry = Number(defaults.retry ?? runForm.retry)
}

function connectivityStatusLabel(status?: string) {
  if (status === 'online') return '사용 가능'
  if (status === 'offline') return '모델 없음'
  if (status === 'error') return '연결 오류'
  if (status === 'skipped') return '비활성'
  return '확인 중'
}

function connectivityStatusClass(status?: string) {
  if (status === 'online') return 'badge-success'
  if (status === 'offline') return 'badge-warning'
  if (status === 'error') return 'badge-danger'
  return 'badge-warning'
}

function getDatasetTypeLabel(value: string) {
  return datasetTypeOptions.find((option) => option.value === value)?.label ?? value
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

function formatDate(value: string | null) {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}

function formatRunConfig(run: EvaluationRun) {
  const config = run.config ?? {}
  const total = config.total_questions ?? config.max_questions ?? '-'
  const seed = config.seed ?? '-'
  return `N=${total} · seed ${seed}`
}

function openWorkspaceTab(tabId: string) {
  window.dispatchEvent(new CustomEvent('open-workspace-tab', { detail: tabId }))
}

function openResults(run: EvaluationRun) {
  sessionStorage.setItem('selected-evaluation-run-id', String(run.id))
  openWorkspaceTab('model-evaluation')
}

const selectedDatasetName = computed(() => selectedDataset.value?.name ?? '데이터셋')

onMounted(loadPageData)
</script>

<template>
  <div class="page-shell">
    <div class="page-header">
      <div>
        <p class="page-label">실험</p>
        <h2 class="page-title">실험 설계 및 실행</h2>
        <p class="page-subtitle">
          연구 목적에 맞게 데이터셋·평가방식·비교 모델을 조합하고, 재현 가능한 설정으로 실험을 설계·실행합니다.
        </p>
      </div>
    </div>

    <div v-if="error" class="alert-error mb-4 whitespace-pre-line">{{ error }}</div>
    <div v-if="message" class="alert-success mb-4">{{ message }}</div>

    <div class="mb-6 grid gap-5 xl:grid-cols-[minmax(0,1fr)_22rem]">
      <form class="section-card-padded" @submit.prevent="createRun">
        <div class="mb-5 flex flex-wrap items-start justify-between gap-3">
          <div>
            <div class="mb-1 flex items-center gap-2">
              <FlaskConicalIcon class="h-4 w-4 text-indigo-400" />
              <h3 class="font-semibold text-zinc-100">새 실험 설계</h3>
            </div>
            <p class="text-xs text-zinc-500">프리셋으로 빠르게 시작하거나, 단계별로 조건을 직접 구성하세요.</p>
          </div>
          <div class="alert-info px-3 py-2 text-xs">
            {{ experimentPresets.find((preset) => preset.id === selectedPreset)?.label ?? '직접 설계' }} ·
            {{ runForm.model_ids.length }}개 모델 · N={{ runForm.total_questions }}
          </div>
        </div>

        <div class="mb-5 grid grid-cols-2 gap-2 md:grid-cols-4">
          <div
            v-for="(step, index) in workflowSteps"
            :key="step.id"
            class="subsection-card flex items-center gap-2 px-3 py-2.5"
          >
            <component :is="step.done ? CheckCircle2Icon : CircleIcon" :class="['h-4 w-4 shrink-0', step.done ? 'text-emerald-400' : 'text-zinc-600']" />
            <div class="min-w-0">
              <p class="text-[10px] uppercase tracking-widest text-zinc-500">{{ index + 1 }}단계</p>
              <p :class="['truncate text-xs font-medium', step.done ? 'text-zinc-200' : 'text-zinc-500']">{{ step.label }}</p>
            </div>
          </div>
        </div>

        <div class="grid gap-5">
          <section class="subsection-card">
            <div class="mb-3 flex items-center gap-2">
              <SparklesIcon class="h-4 w-4 text-indigo-400" />
              <h4 class="text-sm font-semibold text-zinc-200">연구 프리셋</h4>
            </div>
            <div class="grid gap-3 md:grid-cols-2">
              <button
                v-for="preset in experimentPresets"
                :key="preset.id"
                :class="[
                  'surface-muted w-full p-3 text-left transition-colors',
                  selectedPreset === preset.id ? 'preset-card-selected' : 'item-hover'
                ]"
                type="button"
                @click="applyExperimentPreset(preset.id)"
              >
                <div class="mb-2 flex items-center justify-between gap-2">
                  <span class="text-sm font-semibold text-zinc-100">{{ preset.label }}</span>
                  <span :class="['badge shrink-0', selectedPreset === preset.id ? 'badge-primary' : 'badge-muted']">
                    {{ preset.badge }}
                  </span>
                </div>
                <span class="block text-xs leading-5 text-zinc-500">{{ preset.description }}</span>
              </button>
            </div>
          </section>

          <section class="subsection-card">
            <h4 class="mb-3 text-sm font-semibold text-zinc-200">1. 실험 기본 정보</h4>
            <div class="grid gap-4 md:grid-cols-2">
              <label class="block md:col-span-2">
                <span class="ui-label">실험 이름</span>
                <input v-model.trim="runForm.name" placeholder="예: 객관식 벤치마크 모델 비교 (2026-06)" class="ui-input" />
              </label>
              <label class="block md:col-span-2">
                <span class="ui-label">연구 메모</span>
                <textarea
                  v-model.trim="runForm.notes"
                  rows="2"
                  placeholder="비교 목적, 가설, 제외 조건 등을 기록하세요."
                  class="ui-textarea"
                ></textarea>
              </label>
            </div>
          </section>

          <section class="subsection-card">
            <h4 class="mb-3 text-sm font-semibold text-zinc-200">2. 실험 조합</h4>
            <div class="grid gap-4 md:grid-cols-2">
              <label class="block md:col-span-2">
                <span class="ui-label">평가 데이터셋</span>
                <AppSelect v-model="runForm.dataset" :options="datasetOptions" />
                <p v-if="selectedDataset" class="mt-1.5 text-xs text-zinc-500">
                  {{ getDatasetTypeLabel(selectedDataset.dataset_type) }} ·
                  {{ selectedDataset.question_count || '-' }}문항 ·
                  {{ selectedDataset.dataset_family || 'family 미지정' }}
                </p>
              </label>
              <label class="block md:col-span-2">
                <span class="ui-label">평가방식</span>
                <AppSelect v-model="runForm.evaluation_method" :options="methodOptions" @update:model-value="handleMethodChange" />
                <p v-if="selectedMethod" class="mt-1.5 text-xs text-zinc-500">{{ selectedMethod.description || '평가방식 설명 없음' }}</p>
              </label>
            </div>
          </section>

          <section class="subsection-card">
            <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
              <div>
                <div class="flex items-center gap-2">
                  <LayersIcon class="h-4 w-4 text-indigo-400" />
                  <h4 class="text-sm font-semibold text-zinc-200">3. 비교 모델</h4>
                  <span class="badge badge-muted">{{ runForm.model_ids.length }}개 선택</span>
                </div>
                <p class="mt-1 text-xs text-zinc-500">동일 데이터셋·평가방식 안에서 비교할 모델을 선택합니다.</p>
              </div>
              <button
                class="btn-soft-primary shrink-0"
                :disabled="checkingAvailability"
                type="button"
                @click="loadModelAvailability()"
              >
                <RefreshCwIcon :class="['h-3.5 w-3.5', checkingAvailability ? 'animate-spin' : '']" />
                {{ checkingAvailability ? '확인 중...' : '연결 상태 새로고침' }}
              </button>
            </div>

            <div
              v-if="ollamaConnectivityIssue"
              class="alert-info mb-3 border-amber-500/30 bg-amber-500/10 text-xs text-amber-100"
            >
              <div class="mb-1 flex items-center gap-2 font-semibold text-amber-200">
                <ServerIcon class="h-3.5 w-3.5" />
                선택한 로컬 모델을 바로 사용할 수 없습니다
              </div>
              <p>로컬 추론 서버를 실행한 뒤, 필요한 모델이 설치되어 있는지 확인해 주세요.</p>
            </div>

            <div class="space-y-3">
              <div v-for="[provider, providerModels] in modelsByProvider" :key="provider">
                <div class="mb-2 flex items-center justify-between gap-2 px-1">
                  <p class="text-xs font-semibold uppercase tracking-wide text-zinc-500">{{ providerLabels[provider] ?? provider }}</p>
                  <button class="text-xs font-medium text-indigo-300 hover:text-indigo-200" type="button" @click="selectProviderModels(provider)">
                    {{ providerModels.every((model) => runForm.model_ids.includes(model.id)) ? '전체 해제' : '전체 선택' }}
                  </button>
                </div>
                <div class="space-y-2">
                  <button
                    v-for="model in providerModels"
                    :key="model.id"
                    :class="['w-full px-3 py-3 text-left transition', modelRowClass(model.id)]"
                    type="button"
                    @click="toggleModel(model.id)"
                  >
                    <div class="flex items-start justify-between gap-3">
                      <div class="min-w-0 flex-1">
                        <div class="mb-1 flex items-center gap-2">
                          <input
                            :checked="isModelSelected(model.id)"
                            class="checkbox-accent pointer-events-none"
                            type="checkbox"
                            tabindex="-1"
                          />
                          <p class="truncate text-sm font-semibold text-zinc-100">{{ model.display_name }}</p>
                        </div>
                        <p class="truncate text-xs text-zinc-500">{{ model.provider }}/{{ model.name }}</p>
                      </div>
                      <span :class="['badge shrink-0', connectivityStatusClass(connectivityByModelId[model.id]?.status)]">
                        {{ connectivityStatusLabel(connectivityByModelId[model.id]?.status) }}
                      </span>
                    </div>
                  </button>
                </div>
              </div>
              <p v-if="!activeModels.length" class="list-item px-3 py-8 text-center text-sm text-zinc-600">활성 모델이 없습니다. 모델 메뉴에서 등록하세요.</p>
            </div>
          </section>

          <details class="subsection-card">
            <summary class="flex cursor-pointer list-none items-center gap-2 text-sm font-semibold text-zinc-200">
              <SettingsIcon class="h-4 w-4 text-indigo-400" />
              4. 실행 파라미터
              <span class="badge badge-muted">고급</span>
            </summary>
            <p class="alert-info mt-3 text-xs">재현성과 비용·시간 균형을 위해 문항 수, 시드, 응답 길이를 조정합니다.</p>
            <div class="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <label class="block">
                <span class="ui-label">평가 문항 수 (N)</span>
                <input v-model.number="runForm.total_questions" min="1" type="number" placeholder="20" class="ui-input" />
              </label>
              <label class="block">
                <span class="ui-label">재현 시드</span>
                <input v-model.number="runForm.seed" min="0" type="number" class="ui-input" />
              </label>
              <label class="block">
                <span class="ui-label">예시 문항 수 (few-shot)</span>
                <input v-model.number="runForm.few_shot" min="0" type="number" class="ui-input" />
              </label>
              <label class="block">
                <span class="ui-label">생성 온도</span>
                <input v-model.number="runForm.temperature" min="0" max="2" step="0.1" type="number" class="ui-input" />
              </label>
              <label class="block">
                <span class="ui-label">최대 응답 토큰</span>
                <input v-model.number="runForm.max_tokens" min="1" type="number" class="ui-input" />
              </label>
              <label class="block">
                <span class="ui-label">응답 제한 시간(초)</span>
                <input v-model.number="runForm.timeout_seconds" min="1" type="number" class="ui-input" />
              </label>
              <label class="block">
                <span class="ui-label">재시도 횟수</span>
                <input v-model.number="runForm.retry" min="0" type="number" class="ui-input" />
              </label>
            </div>
          </details>
        </div>

        <footer class="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-zinc-800 pt-4">
          <p class="text-xs text-zinc-500">실험 생성 후 아래 기록에서 실행을 시작합니다. 완료되면 결과 분석으로 이동하세요.</p>
          <button class="btn-primary" :disabled="savingRun || !datasets.length || !activeModels.length || !canCreateRun" type="submit">
            <BeakerIcon class="h-4 w-4" />
            {{ savingRun ? '생성 중...' : '실험 생성' }}
          </button>
        </footer>
      </form>

      <aside class="space-y-4">
        <div class="section-card-padded">
          <div class="mb-3 flex items-center gap-2">
            <ClipboardListIcon class="h-4 w-4 text-indigo-400" />
            <h3 class="text-sm font-semibold text-zinc-200">실험 설계 요약</h3>
          </div>
          <div v-if="experimentSummaryCards.length" class="space-y-2">
            <div v-for="card in experimentSummaryCards" :key="card.label" class="subsection-card p-3">
              <p class="text-[10px] uppercase tracking-widest text-zinc-500">{{ card.label }}</p>
              <p class="mt-1 text-sm font-semibold text-zinc-100">{{ card.value }}</p>
              <p class="mt-1 text-xs text-zinc-500">{{ card.sub }}</p>
            </div>
          </div>
          <p v-else class="text-sm text-zinc-600">데이터셋과 평가방식을 선택하면 요약이 표시됩니다.</p>
        </div>

        <div class="section-card-padded">
          <h3 class="mb-3 text-sm font-semibold text-zinc-200">실행 전 체크리스트</h3>
          <ul class="space-y-2">
            <li v-for="check in readinessChecks" :key="check.label" class="flex items-center gap-2 text-sm">
              <component :is="check.ok ? CheckCircle2Icon : CircleIcon" :class="['h-4 w-4 shrink-0', check.ok ? 'text-emerald-400' : 'text-zinc-600']" />
              <span :class="check.ok ? 'text-zinc-300' : 'text-zinc-500'">{{ check.label }}</span>
            </li>
          </ul>
        </div>

        <div class="section-card-padded">
          <h3 class="mb-3 text-sm font-semibold text-zinc-200">다음 단계</h3>
          <div class="space-y-2">
            <button class="btn-soft-primary w-full" type="button" @click="openWorkspaceTab('model-evaluation')">
              <BarChart3Icon class="h-4 w-4" />
              결과 분석 보기
            </button>
            <button class="btn-soft-primary w-full" type="button" @click="openWorkspaceTab('evaluation-datasets')">
              <DatabaseIcon class="h-4 w-4" />
              데이터셋 관리
            </button>
            <button class="btn-soft-primary w-full" type="button" @click="openWorkspaceTab('evaluation-methods')">
              <ClipboardListIcon class="h-4 w-4" />
              평가방식 관리
            </button>
          </div>
        </div>
      </aside>
    </div>

    <section class="section-card-padded">
      <div class="mb-4 flex flex-wrap items-end justify-between gap-4">
        <div>
          <div class="mb-1 flex items-center gap-2">
            <PlayIcon class="h-4 w-4 text-indigo-400" />
            <h3 class="font-semibold text-zinc-100">실험 기록</h3>
            <span class="badge badge-muted">{{ filteredRuns.length }}건</span>
          </div>
          <p class="text-xs text-zinc-500">생성된 실험을 실행하고, 완료 후 결과 분석으로 이동합니다.</p>
        </div>
        <div class="flex flex-wrap gap-2">
          <button
            v-for="option in [
              { value: 'all', label: '전체' },
              { value: 'pending', label: '대기' },
              { value: 'running', label: '실행 중' },
              { value: 'completed', label: '완료' },
              { value: 'failed', label: '실패' },
            ]"
            :key="option.value"
            :class="[
              'rounded-lg border px-3 py-1.5 text-xs font-medium transition',
              statusFilter === option.value
                ? 'border-indigo-500/50 bg-indigo-500/10 text-indigo-300'
                : 'border-zinc-700 text-zinc-400 hover:border-zinc-600 hover:text-zinc-300'
            ]"
            type="button"
            @click="statusFilter = option.value as typeof statusFilter"
          >
            {{ option.label }}
            <span class="ml-1 text-zinc-500">{{ runStatusCounts[option.value as keyof typeof runStatusCounts] }}</span>
          </button>
        </div>
      </div>

      <div class="subsection-card mb-4">
        <div class="relative min-w-72 max-w-xl">
          <SearchIcon class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
          <input v-model="searchQuery" class="ui-input-search" placeholder="실험명, 데이터셋, 평가방식, 상태 검색..." type="text" />
        </div>
      </div>

      <div v-if="loading" class="list-item px-3 py-10 text-center text-sm text-zinc-500">실험 기록을 불러오는 중...</div>

      <div v-else-if="!filteredRuns.length" class="list-item px-3 py-12 text-center">
        <BeakerIcon class="mx-auto mb-3 h-8 w-8 text-zinc-600" />
        <h3 class="text-base font-semibold text-zinc-300">표시할 실험이 없습니다</h3>
        <p class="mt-1 text-sm text-zinc-500">위에서 실험을 설계해 생성하거나, 필터 조건을 바꿔 보세요.</p>
      </div>

      <div v-else class="space-y-2">
        <article
          v-for="run in filteredRuns"
          :key="run.id"
          class="list-item list-item-hover px-3 py-3"
        >
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div class="min-w-0 flex-1">
              <div class="mb-1 flex flex-wrap items-center gap-2">
                <h4 class="truncate text-sm font-semibold text-zinc-100">{{ run.name }}</h4>
                <span :class="['badge shrink-0', statusClass(run.status)]">{{ getStatusLabel(run.status) }}</span>
              </div>
              <p class="truncate text-xs text-zinc-500">
                {{ run.dataset_name }} · {{ getDatasetTypeLabel(run.dataset_type) }} ·
                {{ run.evaluation_method_name || '평가방식 미지정' }}
              </p>
              <p class="mt-1 text-xs text-zinc-600">
                Run #{{ run.id }} · {{ formatRunConfig(run) }} · {{ run.results.length }}개 모델 · 생성 {{ formatDate(run.created_at) }}
              </p>
            </div>

            <div class="flex shrink-0 flex-wrap items-center gap-2">
              <button
                v-if="run.status === 'completed'"
                class="btn-soft-primary"
                type="button"
                @click="openResults(run)"
              >
                <BarChart3Icon class="h-4 w-4" />
                결과 분석
              </button>
              <button
                class="btn-primary"
                :disabled="executingRunId !== null || run.status === 'running' || run.status === 'completed'"
                type="button"
                @click="executeRun(run)"
              >
                <PlayIcon class="h-4 w-4" />
                {{ executingRunId === run.id ? '실행 중...' : run.status === 'completed' ? '완료됨' : '실험 실행' }}
              </button>
              <button
                class="rounded-md p-1.5 text-zinc-500 transition-colors hover:bg-red-900/40 hover:text-red-400 disabled:cursor-not-allowed disabled:opacity-40"
                :disabled="run.status === 'running'"
                title="실험 삭제"
                type="button"
                @click="deleteRun(run)"
              >
                <TrashIcon class="h-4 w-4" />
              </button>
            </div>
          </div>
        </article>
      </div>
    </section>
  </div>
</template>
