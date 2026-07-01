<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { DatabaseIcon, EyeIcon, FileTextIcon, LayersIcon, PlusIcon, SearchIcon, TrashIcon, XIcon } from 'lucide-vue-next'
import AdminDataTable from '../components/common/AdminDataTable.vue'
import AppSelect, { SelectOption } from '../components/common/AppSelect.vue'
import { EvaluationDataset, useApi } from '../composables/useApi'

const api = useApi()
const datasets = ref<EvaluationDataset[]>([])
const loading = ref(false)
const savingDataset = ref(false)
const searchQuery = ref('')
const error = ref('')
const message = ref('')
const selectedDataset = ref<EvaluationDataset | null>(null)

const datasetForm = reactive({
  name: '',
  dataset_type: 'multiple_choice',
  dataset_family: 'mmlu',
  data_format: 'jsonl',
  source: 'url',
  source_url: '',
  original_filename: '',
  description: '',
  raw_content: '',
})

const taskTypeOptions: SelectOption[] = [
  { value: 'multiple_choice', label: '객관식 평가' },
  { value: 'qa', label: 'QA' },
  { value: 'generation', label: '생성/요약' },
  { value: 'rag', label: 'RAG' },
  { value: 'safety_classification', label: '안전성/분류' },
  { value: 'custom', label: '기타/사용자 정의' },
]

const legacyTaskTypeOptions: SelectOption[] = [
  { value: 'mmlu', label: '객관식 평가' },
  { value: 'custom_mcq', label: '객관식 평가' },
  { value: 'jsonl', label: '객관식 평가' },
  { value: 'csv', label: '객관식 평가' },
]

const datasetFamilyOptions: SelectOption[] = [
  { value: 'mmlu', label: 'MMLU' },
  { value: 'custom', label: '사용자 정의' },
  { value: 'humaneval', label: 'HumanEval' },
  { value: 'gsm8k', label: 'GSM8K' },
  { value: 'other', label: '기타' },
]

const dataFormatOptions: SelectOption[] = [
  { value: 'jsonl', label: 'JSONL' },
  { value: 'csv', label: 'CSV' },
  { value: 'json', label: 'JSON' },
  { value: 'txt', label: 'TXT' },
  { value: 'unknown', label: '미정/기타' },
]

const sourceOptions: SelectOption[] = [
  { value: 'upload', label: '직접 업로드' },
  { value: 'url', label: '온라인 URL' },
  { value: 'huggingface', label: 'Hugging Face' },
]

const filteredDatasets = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()
  return datasets.value.filter(
    (dataset) =>
      !query ||
      dataset.name.toLowerCase().includes(query) ||
      dataset.dataset_type.toLowerCase().includes(query) ||
      getDatasetFamilyValue(dataset).toLowerCase().includes(query) ||
      getDataFormatValue(dataset).toLowerCase().includes(query) ||
      dataset.source.toLowerCase().includes(query) ||
      dataset.description.toLowerCase().includes(query)
  )
})

const selectedDatasetSamples = computed(() => {
  if (!selectedDataset.value) {
    return []
  }
  return parseSampleItems(selectedDataset.value)
})

const selectedDatasetOverviewCards = computed(() => {
  if (!selectedDataset.value) {
    return []
  }
  const dataset = selectedDataset.value
  return [
    { label: '문항 수', value: dataset.question_count ? dataset.question_count.toLocaleString() : '-', sub: '등록 시 집계된 문항' },
    { label: '작업 유형', value: getDatasetTypeLabel(dataset.dataset_type), sub: '평가방식 호환 기준' },
    { label: '데이터셋 패밀리', value: getDatasetFamilyLabel(getDatasetFamilyValue(dataset)), sub: '벤치마크/계열' },
    { label: '포맷', value: getDataFormatLabel(getDataFormatValue(dataset)), sub: getSourceLabel(dataset.source) },
  ]
})

async function loadPageData() {
  loading.value = true
  try {
    datasets.value = await api.getEvaluationDatasets()
  } finally {
    loading.value = false
  }
}

async function createDataset() {
  error.value = ''
  message.value = ''
  savingDataset.value = true
  try {
    await api.createEvaluationDataset({
      name: datasetForm.name,
      dataset_type: datasetForm.dataset_type,
      dataset_family: datasetForm.dataset_family,
      data_format: datasetForm.data_format,
      source: datasetForm.source,
      source_url: datasetForm.source_url,
      original_filename: datasetForm.original_filename,
      description: datasetForm.description,
      raw_content: datasetForm.raw_content,
      category_schema: buildCategorySchema(),
    })
    Object.assign(datasetForm, {
      name: '',
      dataset_type: 'multiple_choice',
      dataset_family: 'mmlu',
      data_format: 'jsonl',
      source: 'url',
      source_url: '',
      original_filename: '',
      description: '',
      raw_content: '',
    })
    message.value = '평가 데이터셋이 등록되었습니다.'
    await loadPageData()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '평가 데이터셋을 등록하지 못했습니다.'
  } finally {
    savingDataset.value = false
  }
}

function handleDatasetFileChange(event: Event) {
  error.value = ''
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) {
    return
  }
  const reader = new FileReader()
  reader.onload = () => {
    datasetForm.raw_content = String(reader.result ?? '')
    datasetForm.original_filename = file.name
    datasetForm.source = 'upload'
    datasetForm.source_url = ''
    datasetForm.data_format = detectDataFormat(file.name)
    if (datasetForm.data_format === 'csv' || datasetForm.data_format === 'jsonl') {
      datasetForm.dataset_type = 'multiple_choice'
    }
  }
  reader.onerror = () => {
    error.value = '파일을 읽지 못했습니다. JSONL/CSV/JSON/TXT 텍스트 파일인지 확인하세요.'
  }
  reader.readAsText(file, 'utf-8')
}

function getDatasetTypeLabel(value: string) {
  return [...taskTypeOptions, ...legacyTaskTypeOptions].find((option) => option.value === value)?.label ?? value
}

function getDatasetFamilyLabel(value: string) {
  return datasetFamilyOptions.find((option) => option.value === value)?.label ?? value
}

function getDataFormatLabel(value: string) {
  return dataFormatOptions.find((option) => option.value === value)?.label ?? value.toUpperCase()
}

function getSourceLabel(value: string) {
  return sourceOptions.find((option) => option.value === value)?.label ?? value
}

function openDatasetDetail(dataset: EvaluationDataset) {
  selectedDataset.value = dataset
}

function closeDatasetDetail() {
  selectedDataset.value = null
}

async function deleteDataset(dataset: EvaluationDataset) {
  if (!confirm(`"${dataset.name}" 데이터셋을 삭제할까요?`)) return
  error.value = ''
  try {
    await api.deleteEvaluationDataset(dataset.id)
    if (selectedDataset.value?.id === dataset.id) {
      selectedDataset.value = null
    }
    await loadPageData()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '데이터셋을 삭제하지 못했습니다.'
  }
}

function getDatasetFamilyValue(dataset: EvaluationDataset) {
  if (dataset.dataset_family) {
    return dataset.dataset_family
  }
  if (dataset.dataset_type === 'mmlu') {
    return 'mmlu'
  }
  return String(dataset.category_schema?.dataset_family || dataset.category_schema?.benchmark_name || 'custom')
}

function getDataFormatValue(dataset: EvaluationDataset) {
  if (dataset.data_format) {
    return dataset.data_format
  }
  if (dataset.dataset_type === 'jsonl' || dataset.dataset_type === 'csv') {
    return dataset.dataset_type
  }
  const filename = dataset.original_filename.toLowerCase()
  return detectDataFormat(filename)
}

function detectDataFormat(fileName: string) {
  const normalizedName = fileName.toLowerCase()
  if (normalizedName.endsWith('.csv')) {
    return 'csv'
  }
  if (normalizedName.endsWith('.jsonl')) {
    return 'jsonl'
  }
  if (normalizedName.endsWith('.json')) {
    return 'json'
  }
  if (normalizedName.endsWith('.txt')) {
    return 'txt'
  }
  return 'unknown'
}

function buildCategorySchema() {
  return {
    task_type: datasetForm.dataset_type,
    dataset_family: datasetForm.dataset_family,
    benchmark_name: datasetForm.dataset_family,
    data_format: datasetForm.data_format,
    expected_fields: {
      question: '질문/프롬프트 본문',
      answer: '정답 또는 기대 출력',
      choices: '객관식 선택지 배열 또는 A/B/C/D 컬럼',
      subject: '과목 또는 세부 주제',
      category: '상위 카테고리',
    },
  }
}

function getDatasetMetaRows(dataset: EvaluationDataset) {
  return [
    { label: 'ID', value: String(dataset.id) },
    { label: '등록 방식', value: getSourceLabel(dataset.source) },
    { label: '등록자', value: dataset.uploaded_by_username || '-' },
    { label: '생성 시각', value: formatDate(dataset.created_at) },
    { label: '수정 시각', value: formatDate(dataset.updated_at) },
  ]
}

function getDatasetTypeBadgeClass(value: string) {
  if (value === 'multiple_choice' || value === 'mmlu' || value === 'custom_mcq') return 'badge-primary'
  if (value === 'generation') return 'badge-info'
  if (value === 'rag') return 'badge-warning'
  return 'badge-muted'
}

function getDataFormatBadgeClass(value: string) {
  if (value === 'jsonl' || value === 'json') return 'badge-info'
  if (value === 'csv') return 'badge-success'
  return 'badge-muted'
}

function formatJson(value: unknown) {
  return JSON.stringify(value ?? {}, null, 2)
}

function previewRawContent(value: string) {
  if (!value) {
    return '원문이 저장되어 있지 않습니다.'
  }
  const maxChars = 4000
  const maxLines = 80
  const lines = value.split(/\r?\n/)
  const lineLimited = lines.slice(0, maxLines).join('\n')
  const preview = lineLimited.slice(0, maxChars)
  const omittedLines = lines.length > maxLines
  const omittedChars = lineLimited.length > maxChars || value.length > preview.length
  return `${preview}${omittedLines || omittedChars ? '\n\n... 긴 원문은 일부만 표시했습니다.' : ''}`
}

function parseSampleItems(dataset: EvaluationDataset) {
  const rawContent = dataset.raw_content?.trim()
  if (!rawContent) {
    return []
  }

  const format = getDataFormatValue(dataset)
  if (format === 'jsonl') {
    return rawContent
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean)
      .slice(0, 3)
      .map((line, index) => parseJsonLine(line, index))
  }

  if (format === 'csv') {
    return parseCsvPreview(rawContent)
  }

  if (format === 'json') {
    return parseJsonPreview(rawContent)
  }

  return rawContent
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .slice(0, 3)
    .map((line, index) => ({ line: index + 1, text: line }))
}

function parseJsonLine(line: string, index: number) {
  try {
    return JSON.parse(line) as Record<string, unknown>
  } catch {
    return { line: index + 1, raw: line }
  }
}

function parseJsonPreview(rawContent: string) {
  try {
    const parsed = JSON.parse(rawContent) as unknown
    if (Array.isArray(parsed)) {
      return parsed.slice(0, 3)
    }
    if (parsed && typeof parsed === 'object') {
      const candidateItems = Object.values(parsed as Record<string, unknown>).find((value) => Array.isArray(value))
      return Array.isArray(candidateItems) ? candidateItems.slice(0, 3) : [parsed]
    }
  } catch {
    return []
  }
  return []
}

function parseCsvPreview(rawContent: string) {
  const rows = rawContent
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
  const headers = splitCsvLine(rows[0] ?? '')
  if (!headers.length) {
    return []
  }
  return rows.slice(1, 4).map((row) => {
    const values = splitCsvLine(row)
    return headers.reduce<Record<string, string>>((item, header, index) => {
      item[header || `column_${index + 1}`] = values[index] ?? ''
      return item
    }, {})
  })
}

function splitCsvLine(line: string) {
  const values: string[] = []
  let current = ''
  let inQuotes = false

  for (let index = 0; index < line.length; index += 1) {
    const char = line[index]
    const nextChar = line[index + 1]
    if (char === '"' && nextChar === '"') {
      current += '"'
      index += 1
    } else if (char === '"') {
      inQuotes = !inQuotes
    } else if (char === ',' && !inQuotes) {
      values.push(current)
      current = ''
    } else {
      current += char
    }
  }
  values.push(current)
  return values.map((value) => value.trim())
}

function formatDate(value: string) {
  return new Date(value).toLocaleString()
}

onMounted(() => {
  loadPageData()
  window.addEventListener('reload-evaluation-datasets', loadPageData)
})

onBeforeUnmount(() => {
  window.removeEventListener('reload-evaluation-datasets', loadPageData)
})
</script>

<template>
  <div class="page-shell">
    <div class="page-header">
      <div>
        <p class="page-label">리소스</p>
        <h2 class="page-title">데이터셋</h2>
        <p class="page-subtitle">실험에 사용할 평가 자료를 등록하고 작업 유형, 벤치마크, 가져오기 형식, 문항 수를 분리해 관리합니다.</p>
      </div>
    </div>

    <div v-if="error" class="alert-error mb-4">{{ error }}</div>
    <div v-if="message" class="alert-success mb-4">{{ message }}</div>

    <div class="mb-6 grid gap-5">
      <form class="section-card-padded" @submit.prevent="createDataset">
        <div class="mb-5 flex flex-wrap items-start justify-between gap-3">
          <div>
            <div class="mb-1 flex items-center gap-2">
              <DatabaseIcon class="h-4 w-4 text-indigo-400" />
              <h3 class="font-semibold text-zinc-100">평가 데이터셋 등록</h3>
            </div>
            <p class="text-xs text-zinc-500">MMLU는 벤치마크/데이터셋 패밀리로, JSONL/CSV는 파일 형식으로 선택합니다.</p>
          </div>
          <div class="alert-info px-3 py-2 text-xs">
            현재 선택: {{ getDatasetTypeLabel(datasetForm.dataset_type) }} · {{ getDatasetFamilyLabel(datasetForm.dataset_family) }} · {{ getDataFormatLabel(datasetForm.data_format) }}
          </div>
        </div>
        <div class="grid gap-5">
          <section class="subsection-card">
            <h4 class="mb-3 text-sm font-semibold text-zinc-200">기본 정보</h4>
            <div class="grid gap-4 md:grid-cols-2">
              <label class="block md:col-span-2">
                <span class="mb-1.5 block text-xs font-medium text-zinc-400">데이터셋명</span>
                <input v-model.trim="datasetForm.name" required placeholder="MMLU 카테고리 균형 표본 N=48" class="ui-input" />
              </label>
              <label class="block md:col-span-2">
                <span class="mb-1.5 block text-xs font-medium text-zinc-400">설명</span>
                <textarea v-model.trim="datasetForm.description" rows="2" placeholder="평가 목적, 표본 기준, 과목/카테고리 범위 등을 기록하세요." class="ui-textarea"></textarea>
              </label>
            </div>
          </section>

          <section class="subsection-card grid gap-4 md:grid-cols-2">
            <div class="md:col-span-2">
              <h4 class="text-sm font-semibold text-zinc-200">평가 목적과 데이터셋 계열</h4>
              <p class="mt-1 text-xs text-zinc-500">작업 유형은 평가 방식 호환성에 쓰이고, MMLU/HumanEval/GSM8K는 데이터셋 패밀리로 관리됩니다.</p>
            </div>
            <label class="block">
              <span class="mb-1.5 block text-xs font-medium text-zinc-400">평가 목적/작업 유형</span>
              <AppSelect v-model="datasetForm.dataset_type" :options="taskTypeOptions" />
            </label>
            <label class="block">
              <span class="mb-1.5 block text-xs font-medium text-zinc-400">벤치마크/데이터셋 패밀리</span>
              <AppSelect v-model="datasetForm.dataset_family" :options="datasetFamilyOptions" />
            </label>
          </section>

          <section class="subsection-card grid gap-4 md:grid-cols-2">
            <div class="md:col-span-2">
              <h4 class="text-sm font-semibold text-zinc-200">가져오기 방식과 원문 형식</h4>
              <p class="mt-1 text-xs text-zinc-500">업로드 파일을 선택하면 파일명 확장자로 JSONL/CSV/JSON/TXT 형식을 자동 감지합니다.</p>
            </div>
            <label class="block">
              <span class="mb-1.5 block text-xs font-medium text-zinc-400">가져오기 방식</span>
              <AppSelect v-model="datasetForm.source" :options="sourceOptions" />
            </label>
            <label class="block">
              <span class="mb-1.5 block text-xs font-medium text-zinc-400">파일/원문 형식</span>
              <AppSelect v-model="datasetForm.data_format" :options="dataFormatOptions" />
            </label>
            <label class="block md:col-span-2">
              <span class="mb-1.5 block text-xs font-medium text-zinc-400">URL 또는 Hugging Face 경로</span>
              <input v-model.trim="datasetForm.source_url" :required="datasetForm.source !== 'upload'" placeholder="https://huggingface.co/datasets/cais/mmlu 또는 원문 파일 URL" class="ui-input" />
            </label>
            <label class="block md:col-span-2">
              <span class="mb-1.5 block text-xs font-medium text-zinc-400">파일 업로드</span>
              <input
                accept=".csv,.jsonl,.json,.txt,text/csv,application/json,text/plain"
                class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-300 file:mr-3 file:rounded-md file:border-0 file:bg-zinc-700 file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-zinc-100 hover:file:bg-zinc-600"
                type="file"
                @change="handleDatasetFileChange"
              />
              <p v-if="datasetForm.original_filename" class="mt-1 text-xs text-zinc-500">
                선택된 파일: {{ datasetForm.original_filename }} · 감지된 형식: {{ getDataFormatLabel(datasetForm.data_format) }}
              </p>
            </label>
            <label class="block md:col-span-2">
              <span class="mb-1.5 block text-xs font-medium text-zinc-400">업로드 원문 또는 샘플</span>
              <textarea v-model="datasetForm.raw_content" rows="5" placeholder="JSONL/CSV/JSON/TXT 원문을 붙여넣으면 문항 수를 집계합니다." class="ui-textarea"></textarea>
            </label>
          </section>

          <section class="subsection-card">
            <h4 class="text-sm font-semibold text-zinc-200">스키마 안내</h4>
            <p class="mt-1 text-xs text-zinc-500">객관식 평가에서는 아래 필드를 권장합니다. `subject`와 `category`는 선택 사항이지만 MMLU 같은 벤치마크 분석에 유용합니다.</p>
            <div class="mt-3 grid gap-2 text-xs text-zinc-400 md:grid-cols-5">
              <span class="rounded-md bg-zinc-800 px-2 py-1">question: 질문</span>
              <span class="rounded-md bg-zinc-800 px-2 py-1">answer: 정답</span>
              <span class="rounded-md bg-zinc-800 px-2 py-1">choices: 선택지</span>
              <span class="rounded-md bg-zinc-800 px-2 py-1">subject: 과목</span>
              <span class="rounded-md bg-zinc-800 px-2 py-1">category: 카테고리</span>
            </div>
          </section>
        </div>
        <footer class="mt-4 flex justify-end border-t border-zinc-800 pt-4">
          <button class="btn-primary" :disabled="savingDataset" type="submit">
            <PlusIcon class="h-4 w-4" />
            {{ savingDataset ? '등록 중...' : '데이터셋 등록' }}
          </button>
        </footer>
      </form>

    </div>

    <div class="mb-5 flex flex-wrap items-center gap-3">
      <div class="relative min-w-72 flex-1">
        <SearchIcon class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
        <input v-model="searchQuery" class="ui-input-search" placeholder="데이터셋명, 작업 유형, 벤치마크, 포맷, 설명 검색..." type="text" />
      </div>
    </div>

    <AdminDataTable :loading="loading" :is-empty="filteredDatasets.length === 0">
      <template #head>
        <th class="table-th">데이터셋</th>
        <th class="table-th">작업 유형</th>
        <th class="table-th">벤치마크</th>
        <th class="table-th">포맷</th>
        <th class="table-th">등록 방식</th>
        <th class="table-th">문항 수</th>
        <th class="table-th">등록 시각</th>
        <th class="table-th">상세</th>
        <th class="table-th">삭제</th>
      </template>

      <template #empty>
        <DatabaseIcon class="empty-icon" />
        <h3 class="empty-title">등록된 평가 데이터셋이 없습니다</h3>
        <p class="empty-description">작업 유형, 벤치마크, 파일 형식을 나눠 평가 자료를 등록하세요.</p>
      </template>

      <tr
        v-for="dataset in filteredDatasets"
        :key="dataset.id"
        class="table-row cursor-pointer"
        @click="openDatasetDetail(dataset)"
      >
        <td class="px-5 py-3.5">
          <p class="font-medium text-zinc-200">{{ dataset.name }}</p>
          <p class="max-w-xl truncate text-xs text-zinc-500">{{ dataset.description || dataset.source_url || '-' }}</p>
        </td>
        <td class="whitespace-nowrap px-5 py-3.5 text-sm text-zinc-300">{{ getDatasetTypeLabel(dataset.dataset_type) }}</td>
        <td class="whitespace-nowrap px-5 py-3.5 text-sm text-zinc-300">{{ getDatasetFamilyLabel(getDatasetFamilyValue(dataset)) }}</td>
        <td class="whitespace-nowrap px-5 py-3.5 text-sm text-zinc-300">{{ getDataFormatLabel(getDataFormatValue(dataset)) }}</td>
        <td class="whitespace-nowrap px-5 py-3.5 text-sm text-zinc-400">{{ getSourceLabel(dataset.source) }}</td>
        <td class="whitespace-nowrap px-5 py-3.5 text-sm text-zinc-300">{{ dataset.question_count || '-' }}</td>
        <td class="whitespace-nowrap px-5 py-3.5 text-sm text-zinc-400">{{ formatDate(dataset.created_at) }}</td>
        <td class="whitespace-nowrap px-5 py-3.5">
          <button class="btn-secondary px-3 py-1.5 text-xs" type="button" @click.stop="openDatasetDetail(dataset)">
            <EyeIcon class="h-3.5 w-3.5" />
            상세
          </button>
        </td>
        <td class="whitespace-nowrap px-5 py-3.5">
          <button
            class="rounded-md p-1.5 text-zinc-500 transition-colors hover:bg-red-900/40 hover:text-red-400"
            title="삭제"
            type="button"
            @click.stop="deleteDataset(dataset)"
          >
            <TrashIcon class="h-4 w-4" />
          </button>
        </td>
      </tr>
    </AdminDataTable>

    <div
      v-if="selectedDataset"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
      @click="closeDatasetDetail"
    >
      <section class="section-card max-h-[90vh] w-full max-w-5xl overflow-hidden shadow-2xl" @click.stop>
        <header class="flex items-start justify-between gap-4 border-b border-zinc-800 px-6 py-5">
          <div class="min-w-0">
            <p class="page-label">리소스 · 데이터셋 상세</p>
            <div class="mt-1 flex flex-wrap items-center gap-2">
              <h3 class="text-xl font-bold text-zinc-100">{{ selectedDataset.name }}</h3>
              <span :class="['badge', getDatasetTypeBadgeClass(selectedDataset.dataset_type)]">
                {{ getDatasetTypeLabel(selectedDataset.dataset_type) }}
              </span>
              <span :class="['badge', getDataFormatBadgeClass(getDataFormatValue(selectedDataset))]">
                {{ getDataFormatLabel(getDataFormatValue(selectedDataset)) }}
              </span>
              <span class="badge badge-muted">{{ getDatasetFamilyLabel(getDatasetFamilyValue(selectedDataset)) }}</span>
            </div>
            <p class="page-subtitle mt-2">{{ selectedDataset.description || '설명이 없습니다.' }}</p>
          </div>
          <button class="btn-secondary shrink-0 px-2.5 py-2.5" title="닫기" type="button" @click="closeDatasetDetail">
            <XIcon class="h-5 w-5" />
          </button>
        </header>

        <div class="max-h-[calc(90vh-112px)] space-y-5 overflow-y-auto p-6">
          <section class="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <div v-for="card in selectedDatasetOverviewCards" :key="card.label" class="section-card-padded">
              <p class="text-xs font-semibold uppercase tracking-widest text-zinc-500">{{ card.label }}</p>
              <p class="mt-2 text-2xl font-bold text-zinc-100">{{ card.value }}</p>
              <p class="mt-1 text-xs text-zinc-500">{{ card.sub }}</p>
            </div>
          </section>

          <div class="alert-info text-xs">
            등록 방식 <strong class="font-semibold">{{ getSourceLabel(selectedDataset.source) }}</strong> ·
            문항 수 <strong class="font-semibold">{{ selectedDataset.question_count || 0 }}</strong>개 ·
            수정 시각 <strong class="font-semibold">{{ formatDate(selectedDataset.updated_at) }}</strong>
          </div>

          <div class="grid gap-4 lg:grid-cols-2">
            <section class="subsection-card">
              <div class="mb-3 flex items-center gap-2">
                <DatabaseIcon class="h-4 w-4 text-indigo-400" />
                <h4 class="text-sm font-semibold text-zinc-200">등록 정보</h4>
              </div>
              <dl class="grid gap-3 sm:grid-cols-2">
                <div v-for="row in getDatasetMetaRows(selectedDataset)" :key="row.label" class="surface-muted p-3">
                  <dt class="text-xs font-medium text-zinc-500">{{ row.label }}</dt>
                  <dd class="mt-1 break-words text-sm text-zinc-200">{{ row.value }}</dd>
                </div>
              </dl>
            </section>

            <section class="subsection-card">
              <div class="mb-3 flex items-center gap-2">
                <FileTextIcon class="h-4 w-4 text-indigo-400" />
                <h4 class="text-sm font-semibold text-zinc-200">원본 위치</h4>
              </div>
              <dl class="space-y-3 text-sm">
                <div class="surface-muted p-3">
                  <dt class="text-xs font-medium text-zinc-500">source_url</dt>
                  <dd class="mt-1 break-all text-zinc-300">{{ selectedDataset.source_url || '-' }}</dd>
                </div>
                <div class="surface-muted p-3">
                  <dt class="text-xs font-medium text-zinc-500">original_filename</dt>
                  <dd class="mt-1 break-all text-zinc-300">{{ selectedDataset.original_filename || '-' }}</dd>
                </div>
              </dl>
            </section>
          </div>

          <section class="subsection-card">
            <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
              <div class="flex items-center gap-2">
                <LayersIcon class="h-4 w-4 text-indigo-400" />
                <h4 class="text-sm font-semibold text-zinc-200">category_schema</h4>
              </div>
              <span class="badge badge-muted">스키마 메타데이터</span>
            </div>
            <pre class="code-panel max-h-64">{{ formatJson(selectedDataset.category_schema) }}</pre>
          </section>

          <section class="subsection-card">
            <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
              <div class="flex items-center gap-2">
                <EyeIcon class="h-4 w-4 text-indigo-400" />
                <h4 class="text-sm font-semibold text-zinc-200">샘플 문항 preview</h4>
              </div>
              <span class="badge badge-info">최대 3개</span>
            </div>
            <p class="alert-info mb-3 text-xs">JSONL/CSV/JSON은 앞 3개 문항을 가능한 범위에서 파싱합니다.</p>
            <div v-if="selectedDatasetSamples.length" class="grid gap-3">
              <div
                v-for="(sample, index) in selectedDatasetSamples"
                :key="index"
                class="surface-muted overflow-hidden"
              >
                <div class="flex items-center justify-between border-b border-zinc-800 px-3 py-2">
                  <span class="badge badge-primary">문항 {{ index + 1 }}</span>
                  <span class="text-xs text-zinc-500">{{ getDataFormatLabel(getDataFormatValue(selectedDataset)) }}</span>
                </div>
                <pre class="code-panel max-h-56 border-0">{{ formatJson(sample) }}</pre>
              </div>
            </div>
            <div v-else class="rounded-lg border border-dashed border-zinc-800 px-4 py-8 text-center">
              <p class="empty-title">파싱 가능한 샘플 문항이 없습니다</p>
              <p class="empty-description">raw_content가 비어 있거나 지원하지 않는 형식일 수 있습니다.</p>
            </div>
          </section>

          <section class="subsection-card">
            <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
              <div class="flex items-center gap-2">
                <FileTextIcon class="h-4 w-4 text-indigo-400" />
                <h4 class="text-sm font-semibold text-zinc-200">raw_content preview</h4>
              </div>
              <span class="badge badge-muted">80줄 · 4,000자 제한</span>
            </div>
            <p class="alert-info mb-3 text-xs">긴 원문은 앞부분만 미리보기로 표시합니다. 전체 원문은 등록 시 저장된 내용을 기준으로 합니다.</p>
            <pre class="code-panel max-h-96 whitespace-pre-wrap">{{ previewRawContent(selectedDataset.raw_content) }}</pre>
          </section>
        </div>
      </section>
    </div>
  </div>
</template>
