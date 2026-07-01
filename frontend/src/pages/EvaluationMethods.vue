<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ClipboardListIcon, EyeIcon, LayersIcon, PlusIcon, SearchIcon, SettingsIcon, XIcon } from 'lucide-vue-next'
import AdminDataTable from '../components/common/AdminDataTable.vue'
import AppSelect, { SelectOption } from '../components/common/AppSelect.vue'
import { EvaluationMethod, useApi } from '../composables/useApi'

const api = useApi()
const methods = ref<EvaluationMethod[]>([])
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const message = ref('')
const searchQuery = ref('')
const selectedPreset = ref('multiple_choice')
const selectedMethod = ref<EvaluationMethod | null>(null)

const methodForm = reactive({
  name: '',
  display_name: '',
  method_type: 'multiple_choice',
  description: '',
  compatible_dataset_types: ['mmlu', 'custom_mcq', 'jsonl', 'csv', 'multiple_choice'],
  default_config: {
    seed: 42,
    total_questions: 20,
    few_shot: 0,
    temperature: 0,
    max_tokens: 8,
    timeout_seconds: 120,
    retry: 0,
  },
  metric_schema: '{}',
  artifact_schema: '{}',
  is_active: true,
})

const methodTypeOptions: SelectOption[] = [
  { value: 'multiple_choice', label: '객관식' },
  { value: 'generation', label: '생성형' },
  { value: 'retrieval', label: '검색/검색증강' },
  { value: 'custom', label: '커스텀' },
]

const compatibleDatasetOptions = [
  { value: 'multiple_choice', label: '객관식 평가' },
  { value: 'mmlu', label: 'MMLU' },
  { value: 'custom_mcq', label: '커스텀 객관식' },
  { value: 'jsonl', label: 'JSONL 업로드' },
  { value: 'csv', label: 'CSV 업로드' },
  { value: 'qa', label: 'QA' },
  { value: 'generation', label: '생성/요약' },
  { value: 'rag', label: 'RAG' },
  { value: 'safety_classification', label: '안전성/분류' },
  { value: 'custom', label: '사용자 정의' },
]

const presetOptions = [
  {
    id: 'multiple_choice',
    label: '객관식 정확도 평가',
    description: 'MMLU/CSV/JSONL 객관식 정답률을 빠르게 측정합니다.',
    values: {
      name: 'multiple_choice_accuracy',
      display_name: '객관식 정확도 평가',
      method_type: 'multiple_choice',
      description: '선택지 기반 정답률, 형식 준수율, 지연 시간을 함께 기록합니다.',
      compatible_dataset_types: ['multiple_choice', 'mmlu', 'custom_mcq', 'jsonl', 'csv'],
      default_config: { seed: 42, total_questions: 20, few_shot: 0, temperature: 0, max_tokens: 8, timeout_seconds: 120, retry: 0 },
      metric_schema: '{"accuracy":"number","strict_compliance_rate":"number","latency_ms":"number"}',
      artifact_schema: '{"item_logs":"jsonl","scorecard":"json","report":"markdown"}',
    },
  },
  {
    id: 'generation',
    label: '생성형 응답 평가',
    description: '요약/서술형 응답 품질을 사람이 읽기 쉬운 기준으로 평가합니다.',
    values: {
      name: 'generation_quality',
      display_name: '생성형 응답 평가',
      method_type: 'generation',
      description: '정확성, 충실성, 형식 준수 여부를 기준으로 생성형 응답을 평가합니다.',
      compatible_dataset_types: ['generation', 'qa', 'jsonl', 'custom'],
      default_config: { seed: 42, total_questions: 20, few_shot: 1, temperature: 0.2, max_tokens: 512, timeout_seconds: 180, retry: 1 },
      metric_schema: '{"quality_score":"number","format_ok":"boolean","judge_notes":"string"}',
      artifact_schema: '{"judge_outputs":"jsonl","summary":"markdown"}',
    },
  },
  {
    id: 'rag',
    label: 'RAG 평가',
    description: '검색 근거 포함 답변의 정답성, 근거 충실도, 인용 품질을 확인합니다.',
    values: {
      name: 'rag_grounded_answer',
      display_name: 'RAG 평가',
      method_type: 'retrieval',
      description: '검색 문맥 기반 답변의 groundedness, answer relevance, citation 품질을 평가합니다.',
      compatible_dataset_types: ['rag', 'qa', 'jsonl', 'custom'],
      default_config: { seed: 42, total_questions: 20, few_shot: 0, temperature: 0, max_tokens: 768, timeout_seconds: 240, retry: 1 },
      metric_schema: '{"groundedness":"number","answer_relevance":"number","citation_quality":"number"}',
      artifact_schema: '{"retrieval_traces":"jsonl","rag_report":"markdown"}',
    },
  },
  {
    id: 'custom',
    label: '커스텀 평가',
    description: '데이터셋 구조에 맞춰 호환 대상과 실행값을 직접 조정합니다.',
    values: {
      name: 'custom_evaluation',
      display_name: '커스텀 평가',
      method_type: 'custom',
      description: '프로젝트별 평가 스크립트 또는 수동 판정 기준을 적용합니다.',
      compatible_dataset_types: ['custom'],
      default_config: { seed: 42, total_questions: 10, few_shot: 0, temperature: 0, max_tokens: 256, timeout_seconds: 180, retry: 0 },
      metric_schema: '{}',
      artifact_schema: '{}',
    },
  },
]

const filteredMethods = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()
  return methods.value.filter(
    (method) =>
      !query ||
      method.name.toLowerCase().includes(query) ||
      method.display_name.toLowerCase().includes(query) ||
      method.method_type.toLowerCase().includes(query) ||
      method.description.toLowerCase().includes(query)
  )
})

async function loadMethods() {
  loading.value = true
  try {
    methods.value = await api.getEvaluationMethods()
  } finally {
    loading.value = false
  }
}

async function createMethod() {
  error.value = ''
  message.value = ''
  saving.value = true
  try {
    await api.createEvaluationMethod({
      name: methodForm.name,
      display_name: methodForm.display_name,
      method_type: methodForm.method_type,
      description: methodForm.description,
      compatible_dataset_types: [...methodForm.compatible_dataset_types],
      default_config: buildDefaultConfig(),
      metric_schema: parseJsonField(methodForm.metric_schema, 'metric schema'),
      artifact_schema: parseJsonField(methodForm.artifact_schema, 'artifact schema'),
      is_active: methodForm.is_active,
    })
    applyPreset('multiple_choice')
    methodForm.name = ''
    methodForm.display_name = ''
    methodForm.description = ''
    methodForm.is_active = true
    message.value = '평가방식이 등록되었습니다.'
    await loadMethods()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '평가방식을 등록하지 못했습니다.'
  } finally {
    saving.value = false
  }
}

function applyPreset(presetId: string) {
  const preset = presetOptions.find((option) => option.id === presetId)
  if (!preset) {
    return
  }
  selectedPreset.value = presetId
  methodForm.name = preset.values.name
  methodForm.display_name = preset.values.display_name
  methodForm.method_type = preset.values.method_type
  methodForm.description = preset.values.description
  methodForm.compatible_dataset_types = [...preset.values.compatible_dataset_types]
  Object.assign(methodForm.default_config, preset.values.default_config)
  methodForm.metric_schema = preset.values.metric_schema
  methodForm.artifact_schema = preset.values.artifact_schema
}

function toggleCompatibleDataset(value: string) {
  const index = methodForm.compatible_dataset_types.indexOf(value)
  if (index >= 0) {
    methodForm.compatible_dataset_types.splice(index, 1)
  } else {
    methodForm.compatible_dataset_types.push(value)
  }
}

function buildDefaultConfig() {
  return {
    seed: Number(methodForm.default_config.seed),
    total_questions: Number(methodForm.default_config.total_questions),
    few_shot: Number(methodForm.default_config.few_shot),
    temperature: Number(methodForm.default_config.temperature),
    max_tokens: Number(methodForm.default_config.max_tokens),
    timeout_seconds: Number(methodForm.default_config.timeout_seconds),
    retry: Number(methodForm.default_config.retry),
  }
}

function parseJsonField(value: string, label: string) {
  try {
    return JSON.parse(value || '{}') as Record<string, unknown>
  } catch {
    throw new Error(`${label} JSON 형식을 확인하세요.`)
  }
}

function formatJson(value: unknown) {
  return JSON.stringify(value ?? {}, null, 2)
}

function getMethodTypeLabel(value: string) {
  return methodTypeOptions.find((option) => option.value === value)?.label ?? value
}

function getCompatibleDatasetLabel(value: string) {
  return compatibleDatasetOptions.find((option) => option.value === value)?.label ?? value
}

function getMethodTypeBadgeClass(value: string) {
  if (value === 'multiple_choice') return 'badge-primary'
  if (value === 'generation') return 'badge-info'
  if (value === 'retrieval') return 'badge-warning'
  return 'badge-muted'
}

function formatConfigSummary(config: Record<string, unknown>) {
  const parts = [
    `N=${config.total_questions ?? '-'}`,
    `few_shot=${config.few_shot ?? 0}`,
    `temp=${config.temperature ?? 0}`,
    `max=${config.max_tokens ?? '-'}`,
    `timeout=${config.timeout_seconds ?? '-'}s`,
    `retry=${config.retry ?? 0}`,
  ]
  return parts.join(' · ')
}

function openMethodDetail(method: EvaluationMethod) {
  selectedMethod.value = method
}

function closeMethodDetail() {
  selectedMethod.value = null
}

function getMethodOverviewCards(method: EvaluationMethod) {
  const config = method.default_config ?? {}
  return [
    { label: '평가 유형', value: getMethodTypeLabel(method.method_type), sub: method.name },
    { label: '호환 데이터셋', value: `${method.compatible_dataset_types.length}개`, sub: '선택된 데이터셋 유형' },
    { label: '기본 문항 수', value: String(config.total_questions ?? '-'), sub: `seed ${config.seed ?? '-'}` },
    { label: '실행 파라미터', value: `temp ${config.temperature ?? 0}`, sub: `max ${config.max_tokens ?? '-'} · timeout ${config.timeout_seconds ?? '-'}s` },
  ]
}

onMounted(async () => {
  applyPreset('multiple_choice')
  await loadMethods()
})
</script>

<template>
  <div class="page-shell">
    <div class="page-header">
      <div>
        <p class="page-label">리소스</p>
        <h2 class="page-title">평가방식</h2>
        <p class="page-subtitle">데이터셋과 모델 조합에 적용할 평가 로직, 기본 실행값, 산출물 스키마를 관리합니다.</p>
      </div>
    </div>

    <div v-if="error" class="alert-error mb-4">{{ error }}</div>
    <div v-if="message" class="alert-success mb-4">{{ message }}</div>

    <div class="mb-6 grid gap-5">
      <form class="section-card-padded" @submit.prevent="createMethod">
        <div class="mb-5 flex flex-wrap items-start justify-between gap-3">
          <div>
            <div class="mb-1 flex items-center gap-2">
              <ClipboardListIcon class="h-4 w-4 text-indigo-400" />
              <h3 class="font-semibold text-zinc-100">평가방식 등록</h3>
            </div>
            <p class="text-xs text-zinc-500">프리셋을 고른 뒤 데이터셋 호환성과 실행 기본값만 조정하면 기존 JSON payload로 등록됩니다.</p>
          </div>
          <div class="alert-info px-3 py-2 text-xs">
            현재 프리셋: {{ presetOptions.find((preset) => preset.id === selectedPreset)?.label ?? '-' }} ·
            {{ methodForm.is_active ? '활성' : '비활성' }}
          </div>
        </div>

        <div class="grid gap-5">
          <section class="subsection-card">
            <h4 class="mb-3 text-sm font-semibold text-zinc-200">템플릿/프리셋</h4>
            <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              <button
                v-for="preset in presetOptions"
                :key="preset.id"
                :class="[
                  'surface-muted w-full p-3 text-left transition-colors',
                  selectedPreset === preset.id ? 'preset-card-selected' : 'item-hover'
                ]"
                type="button"
                @click="applyPreset(preset.id)"
              >
                <div class="mb-2 flex items-center justify-between gap-2">
                  <span class="text-sm font-semibold text-zinc-100">{{ preset.label }}</span>
                  <span v-if="selectedPreset === preset.id" class="badge badge-primary">선택됨</span>
                </div>
                <span class="block text-xs leading-5 text-zinc-500">{{ preset.description }}</span>
              </button>
            </div>
          </section>

          <section class="subsection-card">
            <h4 class="mb-3 text-sm font-semibold text-zinc-200">기본 정보</h4>
            <div class="grid gap-4 md:grid-cols-2">
              <label class="block">
                <span class="ui-label">시스템 이름</span>
                <input v-model.trim="methodForm.name" required placeholder="custom_mcq_v1" class="ui-input" />
              </label>
              <label class="block">
                <span class="ui-label">표시명</span>
                <input v-model.trim="methodForm.display_name" required placeholder="커스텀 객관식 평가" class="ui-input" />
              </label>
              <label class="block">
                <span class="ui-label">평가 유형</span>
                <AppSelect v-model="methodForm.method_type" :options="methodTypeOptions" />
              </label>
              <label class="checkbox-label self-end">
                <input v-model="methodForm.is_active" type="checkbox" class="checkbox-accent" />
                활성화
              </label>
              <label class="block md:col-span-2">
                <span class="ui-label">설명</span>
                <textarea v-model.trim="methodForm.description" rows="2" placeholder="평가 목적, 산출 metric, 적용 범위를 기록하세요." class="ui-textarea"></textarea>
              </label>
            </div>
          </section>

          <section class="subsection-card">
            <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
              <div>
                <h4 class="text-sm font-semibold text-zinc-200">호환 데이터셋</h4>
                <p class="mt-1 text-xs text-zinc-500">데이터셋 구성에 따라 이 평가방식이 노출될 대상을 선택합니다.</p>
              </div>
              <span class="badge badge-info">{{ methodForm.compatible_dataset_types.length }}개 선택</span>
            </div>
            <div class="grid gap-2 md:grid-cols-5">
              <label
                v-for="option in compatibleDatasetOptions"
                :key="option.value"
                class="checkbox-chip"
              >
                <input
                  :checked="methodForm.compatible_dataset_types.includes(option.value)"
                  class="checkbox-accent"
                  type="checkbox"
                  @change="toggleCompatibleDataset(option.value)"
                />
                {{ option.label }}
              </label>
            </div>
          </section>

          <section class="subsection-card">
            <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
              <h4 class="text-sm font-semibold text-zinc-200">기본 config</h4>
              <span class="badge badge-muted">실험 실행 기본값</span>
            </div>
            <div class="grid gap-4 md:grid-cols-4">
              <label class="block">
                <span class="ui-label">seed</span>
                <input v-model.number="methodForm.default_config.seed" min="0" type="number" class="ui-input" />
              </label>
              <label class="block">
                <span class="ui-label">total_questions</span>
                <input v-model.number="methodForm.default_config.total_questions" min="1" type="number" class="ui-input" />
              </label>
              <label class="block">
                <span class="ui-label">few_shot</span>
                <input v-model.number="methodForm.default_config.few_shot" min="0" type="number" class="ui-input" />
              </label>
              <label class="block">
                <span class="ui-label">temperature</span>
                <input v-model.number="methodForm.default_config.temperature" max="2" min="0" step="0.1" type="number" class="ui-input" />
              </label>
              <label class="block">
                <span class="ui-label">max_tokens</span>
                <input v-model.number="methodForm.default_config.max_tokens" min="1" type="number" class="ui-input" />
              </label>
              <label class="block">
                <span class="ui-label">timeout_seconds</span>
                <input v-model.number="methodForm.default_config.timeout_seconds" min="1" type="number" class="ui-input" />
              </label>
              <label class="block">
                <span class="ui-label">retry</span>
                <input v-model.number="methodForm.default_config.retry" min="0" type="number" class="ui-input" />
              </label>
            </div>
          </section>

          <details class="subsection-card">
            <summary class="flex cursor-pointer list-none items-center gap-2 text-sm font-semibold text-zinc-200">
              <SettingsIcon class="h-4 w-4 text-indigo-400" />
              고급 설정: metric_schema / artifact_schema
              <span class="badge badge-muted">JSON</span>
            </summary>
            <p class="alert-info mt-3 text-xs">개발자용 스키마 정의입니다. 일반 등록에서는 프리셋 기본값을 그대로 사용해도 됩니다.</p>
            <div class="mt-4 grid gap-4 md:grid-cols-2">
              <label class="block">
                <span class="ui-label">metric schema</span>
                <textarea v-model="methodForm.metric_schema" rows="8" class="ui-textarea font-mono text-xs"></textarea>
              </label>
              <label class="block">
                <span class="ui-label">artifact schema</span>
                <textarea v-model="methodForm.artifact_schema" rows="8" class="ui-textarea font-mono text-xs"></textarea>
              </label>
            </div>
          </details>
        </div>

        <footer class="mt-4 flex justify-end border-t border-zinc-800 pt-4">
          <button class="btn-primary" :disabled="saving" type="submit">
            <PlusIcon class="h-4 w-4" />
            {{ saving ? '등록 중...' : '평가방식 등록' }}
          </button>
        </footer>
      </form>
    </div>

    <div class="mb-5 flex flex-wrap items-center gap-3">
      <div class="relative min-w-72 flex-1">
        <SearchIcon class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
        <input v-model="searchQuery" class="ui-input-search" placeholder="평가방식명, 유형, 설명 검색..." type="text" />
      </div>
    </div>

    <AdminDataTable :loading="loading" :is-empty="filteredMethods.length === 0">
      <template #head>
        <th class="table-th">평가방식</th>
        <th class="table-th">유형</th>
        <th class="table-th">호환 데이터셋</th>
        <th class="table-th">기본 config</th>
        <th class="table-th">상태</th>
        <th class="table-th">상세</th>
      </template>
      <template #empty>
        <ClipboardListIcon class="empty-icon" />
        <h3 class="empty-title">등록된 평가방식이 없습니다</h3>
        <p class="empty-description">프리셋을 선택해 평가방식을 등록하거나 마이그레이션 기본값을 확인하세요.</p>
      </template>
      <tr
        v-for="method in filteredMethods"
        :key="method.id"
        class="table-row cursor-pointer"
        @click="openMethodDetail(method)"
      >
        <td class="px-5 py-3.5">
          <p class="font-medium text-zinc-200">{{ method.display_name }}</p>
          <p class="text-xs text-zinc-500">{{ method.name }}</p>
          <p class="mt-1 max-w-xl truncate text-xs text-zinc-500">{{ method.description || '-' }}</p>
        </td>
        <td class="whitespace-nowrap px-5 py-3.5">
          <span :class="['badge', getMethodTypeBadgeClass(method.method_type)]">
            {{ getMethodTypeLabel(method.method_type) }}
          </span>
        </td>
        <td class="px-5 py-3.5">
          <div class="flex max-w-xs flex-wrap gap-1">
            <span
              v-for="datasetType in method.compatible_dataset_types.slice(0, 4)"
              :key="datasetType"
              class="badge badge-muted"
            >
              {{ getCompatibleDatasetLabel(datasetType) }}
            </span>
            <span v-if="method.compatible_dataset_types.length > 4" class="badge badge-muted">
              +{{ method.compatible_dataset_types.length - 4 }}
            </span>
          </div>
        </td>
        <td class="px-5 py-3.5 text-sm text-zinc-400">
          {{ formatConfigSummary(method.default_config) }}
        </td>
        <td class="whitespace-nowrap px-5 py-3.5">
          <span :class="['badge', method.is_active ? 'badge-success' : 'badge-muted']">
            {{ method.is_active ? '활성' : '비활성' }}
          </span>
        </td>
        <td class="whitespace-nowrap px-5 py-3.5">
          <button class="btn-secondary px-3 py-1.5 text-xs" type="button" @click.stop="openMethodDetail(method)">
            <EyeIcon class="h-3.5 w-3.5" />
            상세
          </button>
        </td>
      </tr>
    </AdminDataTable>

    <div
      v-if="selectedMethod"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
      @click="closeMethodDetail"
    >
      <section class="section-card max-h-[90vh] w-full max-w-5xl overflow-hidden shadow-2xl" @click.stop>
        <header class="flex items-start justify-between gap-4 border-b border-zinc-800 px-6 py-5">
          <div class="min-w-0">
            <p class="page-label">리소스 · 평가방식 상세</p>
            <div class="mt-1 flex flex-wrap items-center gap-2">
              <h3 class="text-xl font-bold text-zinc-100">{{ selectedMethod.display_name }}</h3>
              <span :class="['badge', getMethodTypeBadgeClass(selectedMethod.method_type)]">
                {{ getMethodTypeLabel(selectedMethod.method_type) }}
              </span>
              <span :class="['badge', selectedMethod.is_active ? 'badge-success' : 'badge-muted']">
                {{ selectedMethod.is_active ? '활성' : '비활성' }}
              </span>
            </div>
            <p class="page-subtitle mt-2">{{ selectedMethod.description || '설명이 없습니다.' }}</p>
          </div>
          <button class="btn-secondary shrink-0 px-2.5 py-2.5" title="닫기" type="button" @click="closeMethodDetail">
            <XIcon class="h-5 w-5" />
          </button>
        </header>

        <div class="max-h-[calc(90vh-112px)] space-y-5 overflow-y-auto p-6">
          <section class="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <div v-for="card in getMethodOverviewCards(selectedMethod)" :key="card.label" class="section-card-padded">
              <p class="text-xs font-semibold uppercase tracking-widest text-zinc-500">{{ card.label }}</p>
              <p class="mt-2 text-2xl font-bold text-zinc-100">{{ card.value }}</p>
              <p class="mt-1 text-xs text-zinc-500">{{ card.sub }}</p>
            </div>
          </section>

          <div class="alert-info text-xs">
            시스템 이름 <strong class="font-semibold">{{ selectedMethod.name }}</strong> ·
            호환 데이터셋 <strong class="font-semibold">{{ selectedMethod.compatible_dataset_types.length }}</strong>개 ·
            수정 시각 <strong class="font-semibold">{{ new Date(selectedMethod.updated_at).toLocaleString() }}</strong>
          </div>

          <section class="subsection-card">
            <div class="mb-3 flex items-center gap-2">
              <LayersIcon class="h-4 w-4 text-indigo-400" />
              <h4 class="text-sm font-semibold text-zinc-200">호환 데이터셋</h4>
            </div>
            <div class="flex flex-wrap gap-2">
              <span
                v-for="datasetType in selectedMethod.compatible_dataset_types"
                :key="datasetType"
                class="badge badge-muted"
              >
                {{ getCompatibleDatasetLabel(datasetType) }}
              </span>
              <span v-if="!selectedMethod.compatible_dataset_types.length" class="text-sm text-zinc-500">호환 데이터셋이 없습니다.</span>
            </div>
          </section>

          <section class="subsection-card">
            <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
              <div class="flex items-center gap-2">
                <SettingsIcon class="h-4 w-4 text-indigo-400" />
                <h4 class="text-sm font-semibold text-zinc-200">기본 config</h4>
              </div>
              <span class="badge badge-primary">실행 기본값</span>
            </div>
            <dl class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <div
                v-for="(value, key) in selectedMethod.default_config"
                :key="key"
                class="surface-muted p-3"
              >
                <dt class="text-xs font-medium text-zinc-500">{{ key }}</dt>
                <dd class="mt-1 text-sm text-zinc-200">{{ value }}</dd>
              </div>
            </dl>
          </section>

          <section class="subsection-card">
            <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
              <h4 class="text-sm font-semibold text-zinc-200">고급 스키마</h4>
              <span class="badge badge-muted">JSON</span>
            </div>
            <div class="grid gap-4 md:grid-cols-2">
              <div>
                <p class="ui-label">metric_schema</p>
                <pre class="code-panel max-h-56">{{ formatJson(selectedMethod.metric_schema) }}</pre>
              </div>
              <div>
                <p class="ui-label">artifact_schema</p>
                <pre class="code-panel max-h-56">{{ formatJson(selectedMethod.artifact_schema) }}</pre>
              </div>
            </div>
          </section>
        </div>
      </section>
    </div>
  </div>
</template>
