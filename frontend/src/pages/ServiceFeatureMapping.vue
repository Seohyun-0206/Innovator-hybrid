<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { DatabaseIcon, EditIcon, NetworkIcon, PlusIcon, SearchIcon, TrashIcon, UploadCloudIcon, XIcon } from 'lucide-vue-next'
import AdminDataTable from '../components/common/AdminDataTable.vue'
import AppSelect, { SelectOption } from '../components/common/AppSelect.vue'
import { EvaluationDatasetPayload, ServiceFeature, ServiceFeaturePayload, useApi } from '../composables/useApi'

const api = useApi()
const features = ref<ServiceFeature[]>([])
const loading = ref(false)
const searchQuery = ref('')
const error = ref('')
const showModal = ref(false)
const selected = ref<ServiceFeature | null>(null)
const saving = ref(false)

// 데이터셋 업로드 모달 상태
const showDatasetModal = ref(false)
const datasetTarget = ref<ServiceFeature | null>(null)
const savingDataset = ref(false)
const datasetError = ref('')
const datasetMessage = ref('')
const datasetForm = reactive<EvaluationDatasetPayload>({
  name: '',
  dataset_type: 'multiple_choice',
  dataset_family: 'custom',
  data_format: 'jsonl',
  source: 'upload',
  source_url: '',
  original_filename: '',
  description: '',
  raw_content: '',
  category_schema: {},
})

const TIER_CHOICES: SelectOption[] = [
  { value: 'lightweight', label: 'Lightweight' },
  { value: 'standard', label: 'Standard' },
  { value: 'advanced', label: 'Advanced' },
  { value: 'long_context', label: 'Long Context' },
  { value: 'structured', label: 'Structured' },
]
const PATH_CHOICES: SelectOption[] = [
  { value: 'lightweight', label: 'Lightweight Path' },
  { value: 'standard', label: 'Standard Path' },
  { value: 'advanced', label: 'Advanced Path' },
  { value: 'long_context', label: 'Long Context Path' },
  { value: 'structured', label: 'Structured Path' },
  { value: 'escalation', label: 'Escalation Path' },
  { value: 'fallback', label: 'Fallback Path' },
]
const CONDITION_CHOICES: SelectOption[] = [
  { value: 'general', label: 'General / simple query' },
  { value: 'code', label: 'Code or technical' },
  { value: 'reasoning', label: 'Reasoning' },
  { value: 'long_context', label: 'Long context' },
  { value: 'structured_output', label: 'Structured output (SQL/JSON)' },
  { value: 'sensitive', label: 'Sensitive data' },
  { value: 'always', label: 'Always' },
]
const DATASET_TYPE_CHOICES: SelectOption[] = [
  { value: 'multiple_choice', label: '객관식 평가' },
  { value: 'qa', label: 'QA' },
  { value: 'generation', label: '생성/요약' },
  { value: 'rag', label: 'RAG' },
  { value: 'safety_classification', label: '안전성/분류' },
  { value: 'custom', label: '기타/사용자 정의' },
]
const DATA_FORMAT_CHOICES: SelectOption[] = [
  { value: 'jsonl', label: 'JSONL' },
  { value: 'csv', label: 'CSV' },
  { value: 'json', label: 'JSON' },
  { value: 'txt', label: 'TXT' },
]
const SOURCE_CHOICES: SelectOption[] = [
  { value: 'upload', label: '파일 업로드' },
  { value: 'url', label: 'URL' },
]

const TIER_COLORS: Record<string, string> = {
  lightweight: 'border-emerald-500/20 bg-emerald-500/10 text-emerald-400',
  standard: 'border-sky-500/20 bg-sky-500/10 text-sky-300',
  advanced: 'border-violet-500/20 bg-violet-500/10 text-violet-400',
  long_context: 'border-amber-500/20 bg-amber-500/10 text-amber-400',
  structured: 'border-rose-500/20 bg-rose-500/10 text-rose-400',
}

const form = ref<ServiceFeaturePayload>({
  name: '', description: '', required_tier: 'standard', routing_path: 'standard',
  condition_key: 'general', main_metrics: [], sort_order: 100, is_active: true,
})
const metricsInput = ref('')

const filtered = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  return features.value.filter(
    (f) => !q || f.name.toLowerCase().includes(q) || f.required_tier.includes(q) || f.condition_key.includes(q)
  )
})

async function load() {
  loading.value = true
  try {
    features.value = await api.getServiceFeatures()
  } finally {
    loading.value = false
  }
}

function openCreate() {
  selected.value = null
  form.value = { name: '', description: '', required_tier: 'standard', routing_path: 'standard', condition_key: 'general', main_metrics: [], sort_order: 100, is_active: true }
  metricsInput.value = ''
  showModal.value = true
}

function openEdit(f: ServiceFeature) {
  selected.value = f
  form.value = { name: f.name, description: f.description, required_tier: f.required_tier, routing_path: f.routing_path, condition_key: f.condition_key, main_metrics: [...f.main_metrics], sort_order: f.sort_order, is_active: f.is_active }
  metricsInput.value = f.main_metrics.join(', ')
  showModal.value = true
}

function closeModal() { showModal.value = false; selected.value = null }

async function save() {
  saving.value = true
  error.value = ''
  try {
    form.value.main_metrics = metricsInput.value.split(',').map((s) => s.trim()).filter(Boolean)
    if (selected.value) {
      await api.updateServiceFeature(selected.value.id, form.value)
    } else {
      await api.createServiceFeature(form.value)
    }
    closeModal()
    await load()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to save'
  } finally {
    saving.value = false
  }
}

async function remove(f: ServiceFeature) {
  if (!confirm(`"${f.name}" 대상 서비스를 삭제할까요?`)) return
  try {
    await api.deleteServiceFeature(f.id)
    await load()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to delete'
  }
}

// 데이터셋 업로드 모달
function openDatasetUpload(f: ServiceFeature) {
  datasetTarget.value = f
  datasetError.value = ''
  datasetMessage.value = ''
  Object.assign(datasetForm, {
    name: `${f.name} 데이터셋`,
    dataset_type: 'multiple_choice',
    dataset_family: 'custom',
    data_format: 'jsonl',
    source: 'upload',
    source_url: '',
    original_filename: '',
    description: f.description ? `${f.name} 서비스용 평가 데이터셋` : '',
    raw_content: '',
    category_schema: {},
  })
  showDatasetModal.value = true
}

function closeDatasetModal() {
  showDatasetModal.value = false
  datasetTarget.value = null
  datasetError.value = ''
  datasetMessage.value = ''
}

function handleDatasetFile(event: Event) {
  datasetError.value = ''
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = () => {
    datasetForm.raw_content = String(reader.result ?? '')
    datasetForm.original_filename = file.name
    datasetForm.source = 'upload'
    datasetForm.source_url = ''
    datasetForm.data_format = detectFormat(file.name)
  }
  reader.onerror = () => {
    datasetError.value = '파일을 읽지 못했습니다. JSONL/CSV/JSON/TXT 파일인지 확인하세요.'
  }
  reader.readAsText(file, 'utf-8')
}

function detectFormat(fileName: string): string {
  const name = fileName.toLowerCase()
  if (name.endsWith('.csv')) return 'csv'
  if (name.endsWith('.jsonl')) return 'jsonl'
  if (name.endsWith('.json')) return 'json'
  if (name.endsWith('.txt')) return 'txt'
  return 'jsonl'
}

async function saveDataset() {
  datasetError.value = ''
  datasetMessage.value = ''
  if (!datasetForm.name.trim()) {
    datasetError.value = '데이터셋 이름을 입력하세요.'
    return
  }
  if (!datasetForm.raw_content.trim() && !datasetForm.source_url.trim()) {
    datasetError.value = '파일을 업로드하거나 URL 또는 내용을 입력하세요.'
    return
  }
  savingDataset.value = true
  try {
    await api.createEvaluationDataset({ ...datasetForm })
    datasetMessage.value = `"${datasetForm.name}" 데이터셋이 등록되었습니다.`
    window.dispatchEvent(new CustomEvent('reload-evaluation-datasets'))
  } catch (err) {
    datasetError.value = err instanceof Error ? err.message : '데이터셋 등록에 실패했습니다.'
  } finally {
    savingDataset.value = false
  }
}

function goToDatasets() {
  window.dispatchEvent(new CustomEvent('open-workspace-tab', { detail: 'evaluation-datasets' }))
  closeDatasetModal()
}

onMounted(load)
</script>

<template>
  <div class="p-6 lg:p-8">
    <div class="mb-6 flex items-center justify-between gap-4">
      <div>
        <p class="mb-1 text-xs font-semibold uppercase tracking-widest text-indigo-400">정책 설계</p>
        <h2 class="text-2xl font-bold text-zinc-100">대상 서비스</h2>
        <p class="mt-1 text-sm text-zinc-500">대상 서비스별 필요 Tier와 라우팅 경로를 정의합니다.</p>
      </div>
      <button
        class="flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-indigo-500/20 transition hover:bg-indigo-500"
        type="button"
        @click="openCreate"
      >
        <PlusIcon class="h-4 w-4" /> 대상 서비스 추가
      </button>
    </div>

    <div class="mb-5 relative">
      <SearchIcon class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
      <input v-model="searchQuery" class="w-full max-w-sm rounded-lg border border-zinc-700 bg-zinc-800 py-2.5 pl-9 pr-4 text-sm text-zinc-200 placeholder-zinc-600 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50" placeholder="대상 서비스 검색..." type="text" />
    </div>

    <div v-if="error" class="mb-4 rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2.5 text-sm text-red-400">{{ error }}</div>

    <AdminDataTable :loading="loading" :is-empty="filtered.length === 0">
      <template #head>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">대상 서비스</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">필요 Tier</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">라우팅 경로</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">조건</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">주요 지표</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">상태</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">작업</th>
      </template>

      <template #empty>
        <NetworkIcon class="mx-auto mb-4 h-12 w-12 text-zinc-700" />
        <h3 class="mb-1 text-sm font-semibold text-zinc-300">등록된 대상 서비스가 없습니다</h3>
        <p class="mb-4 text-sm text-zinc-600">정책에 사용할 대상 서비스를 추가하세요.</p>
        <button class="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500" @click="openCreate">대상 서비스 추가</button>
      </template>

      <tr v-for="f in filtered" :key="f.id" class="table-row">
        <td class="px-5 py-3.5">
          <p class="font-medium text-zinc-200">{{ f.name }}</p>
          <p class="max-w-xs truncate text-xs text-zinc-500">{{ f.description || '-' }}</p>
        </td>
        <td class="whitespace-nowrap px-5 py-3.5">
          <span :class="['rounded-md border px-2 py-0.5 text-xs font-medium', TIER_COLORS[f.required_tier] ?? 'border-zinc-700 bg-zinc-800 text-zinc-300']">{{ f.required_tier }}</span>
        </td>
        <td class="whitespace-nowrap px-5 py-3.5 text-sm text-zinc-300">{{ f.routing_path }}</td>
        <td class="whitespace-nowrap px-5 py-3.5 text-sm text-zinc-400">{{ f.condition_key }}</td>
        <td class="px-5 py-3.5">
          <div class="flex flex-wrap gap-1">
            <span v-for="metric in f.main_metrics" :key="metric" class="rounded border border-zinc-700 bg-zinc-800 px-1.5 py-0.5 text-xs text-zinc-400">{{ metric }}</span>
            <span v-if="!f.main_metrics.length" class="text-xs text-zinc-600">-</span>
          </div>
        </td>
        <td class="whitespace-nowrap px-5 py-3.5">
          <span :class="['rounded-md border px-2 py-0.5 text-xs font-medium', f.is_active ? 'border-emerald-500/20 bg-emerald-500/10 text-emerald-400' : 'border-zinc-700 bg-zinc-800 text-zinc-500']">{{ f.is_active ? '활성' : '비활성' }}</span>
        </td>
        <td class="whitespace-nowrap px-5 py-3.5">
          <div class="flex items-center gap-1">
            <button
              class="flex items-center gap-1.5 rounded-md border border-indigo-500/30 bg-indigo-500/10 px-2.5 py-1.5 text-xs font-medium text-indigo-300 transition-colors hover:bg-indigo-500/20 hover:text-indigo-200"
              title="데이터셋 업로드"
              type="button"
              @click="openDatasetUpload(f)"
            >
              <DatabaseIcon class="h-3.5 w-3.5" />
              데이터셋
            </button>
            <button class="rounded-md p-1.5 text-zinc-500 transition-colors hover:bg-zinc-700 hover:text-zinc-200" title="수정" type="button" @click="openEdit(f)"><EditIcon class="h-4 w-4" /></button>
            <button class="rounded-md p-1.5 text-zinc-500 transition-colors hover:bg-red-900/40 hover:text-red-400" title="삭제" type="button" @click="remove(f)"><TrashIcon class="h-4 w-4" /></button>
          </div>
        </td>
      </tr>
    </AdminDataTable>

    <!-- 서비스 기능 추가/수정 모달 -->
    <div v-if="showModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div class="w-full max-w-lg rounded-xl border border-zinc-700 bg-zinc-900 shadow-2xl">
        <div class="border-b border-zinc-800 px-6 py-4">
          <h3 class="text-base font-semibold text-zinc-100">{{ selected ? '대상 서비스 수정' : '대상 서비스 추가' }}</h3>
        </div>
        <div class="space-y-4 p-6">
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">이름</span>
            <input v-model="form.name" class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50" />
          </label>
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">설명</span>
            <textarea v-model="form.description" rows="2" class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50" />
          </label>
          <div class="grid grid-cols-2 gap-4">
            <label class="block">
              <span class="mb-1.5 block text-xs font-medium text-zinc-400">필요 Tier</span>
              <AppSelect v-model="form.required_tier" :options="TIER_CHOICES" />
            </label>
            <label class="block">
              <span class="mb-1.5 block text-xs font-medium text-zinc-400">라우팅 경로</span>
              <AppSelect v-model="form.routing_path" :options="PATH_CHOICES" />
            </label>
          </div>
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">조건 키</span>
            <AppSelect v-model="form.condition_key" :options="CONDITION_CHOICES" />
          </label>
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">주요 지표 <span class="text-zinc-600">(쉼표로 구분)</span></span>
            <input v-model="metricsInput" class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50" placeholder="Accuracy, Latency, Format Success Rate" />
          </label>
          <div class="grid grid-cols-2 gap-4">
            <label class="block">
              <span class="mb-1.5 block text-xs font-medium text-zinc-400">정렬 순서</span>
              <input v-model.number="form.sort_order" type="number" class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50" />
            </label>
            <label class="flex items-center gap-3 pt-6">
              <input v-model="form.is_active" type="checkbox" class="h-4 w-4 rounded border-zinc-600 bg-zinc-800 text-indigo-600" />
              <span class="text-sm text-zinc-300">활성</span>
            </label>
          </div>
        </div>
        <div class="flex justify-end gap-3 border-t border-zinc-800 px-6 py-4">
          <button class="rounded-lg border border-zinc-700 px-4 py-2 text-sm text-zinc-300 hover:bg-zinc-800" type="button" @click="closeModal">취소</button>
          <button class="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-50" :disabled="saving || !form.name" type="button" @click="save">
            {{ saving ? '저장 중...' : '저장' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 데이터셋 업로드 모달 -->
    <div v-if="showDatasetModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
      <div class="w-full max-w-xl rounded-xl border border-zinc-700 bg-zinc-900 shadow-2xl">
        <div class="flex items-center justify-between border-b border-zinc-800 px-6 py-4">
          <div>
            <h3 class="text-base font-semibold text-zinc-100">데이터셋 업로드</h3>
            <p class="mt-0.5 text-xs text-zinc-500">{{ datasetTarget?.name }} 서비스에 사용할 평가 데이터를 등록합니다.</p>
          </div>
          <button class="rounded-md p-1.5 text-zinc-500 hover:bg-zinc-800 hover:text-zinc-300" type="button" @click="closeDatasetModal">
            <XIcon class="h-4 w-4" />
          </button>
        </div>

        <div class="space-y-4 p-6">
          <div v-if="datasetError" class="rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2.5 text-sm text-red-400">{{ datasetError }}</div>
          <div v-if="datasetMessage" class="flex items-center justify-between gap-3 rounded-lg border border-emerald-500/20 bg-emerald-500/10 px-3 py-2.5">
            <span class="text-sm text-emerald-400">{{ datasetMessage }}</span>
            <button
              class="shrink-0 rounded-md border border-emerald-500/30 px-3 py-1 text-xs font-semibold text-emerald-300 hover:bg-emerald-500/20"
              type="button"
              @click="goToDatasets"
            >
              데이터셋 탭에서 확인 →
            </button>
          </div>

          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">데이터셋 이름 <span class="text-red-400">*</span></span>
            <input
              v-model="datasetForm.name"
              class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50"
              placeholder="데이터셋 이름을 입력하세요"
            />
          </label>

          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">설명</span>
            <textarea
              v-model="datasetForm.description"
              rows="2"
              class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50"
              placeholder="평가 목적, 데이터 출처 등을 간략히 기록하세요."
            />
          </label>

          <div class="grid grid-cols-2 gap-4">
            <label class="block">
              <span class="mb-1.5 block text-xs font-medium text-zinc-400">평가 유형</span>
              <AppSelect v-model="datasetForm.dataset_type" :options="DATASET_TYPE_CHOICES" />
            </label>
            <label class="block">
              <span class="mb-1.5 block text-xs font-medium text-zinc-400">가져오기 방식</span>
              <AppSelect v-model="datasetForm.source" :options="SOURCE_CHOICES" />
            </label>
          </div>

          <!-- 파일 업로드 -->
          <label v-if="datasetForm.source === 'upload'" class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">파일 선택 <span class="text-zinc-600">(JSONL / CSV / JSON / TXT)</span></span>
            <div class="flex items-center gap-3 rounded-lg border border-dashed border-zinc-700 bg-zinc-800/50 px-4 py-4 transition hover:border-indigo-500/50">
              <UploadCloudIcon class="h-6 w-6 shrink-0 text-zinc-500" />
              <div class="min-w-0 flex-1">
                <p v-if="datasetForm.original_filename" class="truncate text-sm font-medium text-zinc-200">{{ datasetForm.original_filename }}</p>
                <p v-else class="text-sm text-zinc-500">파일을 선택하거나 아래에 직접 붙여넣으세요.</p>
                <p v-if="datasetForm.original_filename" class="text-xs text-zinc-500">감지된 형식: {{ datasetForm.data_format.toUpperCase() }}</p>
              </div>
              <label class="shrink-0 cursor-pointer rounded-md border border-zinc-600 bg-zinc-700 px-3 py-1.5 text-xs font-semibold text-zinc-200 hover:bg-zinc-600">
                파일 선택
                <input
                  accept=".csv,.jsonl,.json,.txt,text/csv,application/json,text/plain"
                  class="sr-only"
                  type="file"
                  @change="handleDatasetFile"
                />
              </label>
            </div>
          </label>

          <!-- URL 입력 -->
          <label v-if="datasetForm.source === 'url'" class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">데이터셋 URL <span class="text-red-400">*</span></span>
            <input
              v-model="datasetForm.source_url"
              class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50"
              placeholder="https://..."
              type="url"
            />
            <label class="mt-2 block">
              <span class="mb-1.5 block text-xs font-medium text-zinc-400">파일 형식</span>
              <AppSelect v-model="datasetForm.data_format" :options="DATA_FORMAT_CHOICES" />
            </label>
          </label>

          <!-- 직접 붙여넣기 -->
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">
              내용 직접 입력
              <span class="text-zinc-600 font-normal">(파일 업로드 없이 붙여넣기 가능)</span>
            </span>
            <textarea
              v-model="datasetForm.raw_content"
              rows="5"
              class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 font-mono text-xs text-zinc-300 outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50"
              placeholder='{"question": "...", "choices": ["A", "B", "C", "D"], "answer": "A"}'
            />
          </label>

          <div class="rounded-lg border border-zinc-800 bg-zinc-800/40 px-3 py-2.5 text-xs text-zinc-500">
            객관식 평가는 <code class="text-zinc-400">question</code> · <code class="text-zinc-400">choices</code> · <code class="text-zinc-400">answer</code> 필드를 포함한 JSONL 또는 CSV를 권장합니다.
          </div>
        </div>

        <div class="flex justify-end gap-3 border-t border-zinc-800 px-6 py-4">
          <button class="rounded-lg border border-zinc-700 px-4 py-2 text-sm text-zinc-300 hover:bg-zinc-800" type="button" @click="closeDatasetModal">취소</button>
          <button
            class="flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-50"
            :disabled="savingDataset || !datasetForm.name.trim()"
            type="button"
            @click="saveDataset"
          >
            <DatabaseIcon class="h-4 w-4" />
            {{ savingDataset ? '등록 중...' : '데이터셋 등록' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
