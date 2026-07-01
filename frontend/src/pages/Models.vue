<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { EditIcon, PlusIcon, RefreshCwIcon, SearchIcon, ServerIcon } from 'lucide-vue-next'
import AdminDataTable from '../components/common/AdminDataTable.vue'
import PaginationControls from '../components/common/PaginationControls.vue'
import ModelModal from '../components/modals/ModelModal.vue'
import AppSelect from '../components/common/AppSelect.vue'
import { LLMModel, LLMModelPayload, ModelConnectivity, ProviderCredential, useApi } from '../composables/useApi'
import { usePagination } from '../composables/usePagination'

const api = useApi()
const models = ref<LLMModel[]>([])
const credentials = ref<ProviderCredential[]>([])
const selectedModel = ref<LLMModel | null>(null)
const showModal = ref(false)
const loading = ref(false)
const connectivityLoading = ref(false)
const searchQuery = ref('')
const statusFilter = ref<'all' | 'active' | 'inactive'>('all')
const error = ref('')
const connectivityError = ref('')
const connectivity = ref<Record<number, ModelConnectivity>>({})

const filteredModels = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()
  return models.value.filter((model) => {
    const matchesQuery =
      !query ||
      model.name.toLowerCase().includes(query) ||
      model.display_name.toLowerCase().includes(query) ||
      model.provider.toLowerCase().includes(query) ||
      model.model_tier.toLowerCase().includes(query) ||
      model.health_status.toLowerCase().includes(query) ||
      model.health_reason.toLowerCase().includes(query) ||
      model.role.toLowerCase().includes(query)
    const matchesStatus =
      statusFilter.value === 'all' ||
      (statusFilter.value === 'active' && model.is_active) ||
      (statusFilter.value === 'inactive' && !model.is_active)
    return matchesQuery && matchesStatus
  })
})
const {
  page,
  pageSize,
  pageSizeOptions,
  totalItems,
  totalPages,
  startItem,
  endItem,
  paginatedItems: paginatedModels
} = usePagination(filteredModels)

async function loadModels() {
  loading.value = true
  try {
    const [loadedModels, loadedCredentials] = await Promise.all([
      api.getModels(),
      api.getProviderCredentials()
    ])
    models.value = loadedModels
    credentials.value = loadedCredentials
  } finally {
    loading.value = false
  }
}

async function refreshConnectivity() {
  connectivityLoading.value = true
  connectivityError.value = ''
  try {
    const results = await api.getModelConnectivity()
    connectivity.value = Object.fromEntries(results.map((result) => [result.model_id, result]))
  } catch (err) {
    connectivityError.value = err instanceof Error ? err.message : '모델 연동 상태를 갱신하지 못했습니다.'
  } finally {
    connectivityLoading.value = false
  }
}

function getConnectivity(model: LLMModel) {
  return connectivity.value[model.id] ?? null
}

function getConnectivityLabel(model: LLMModel) {
  const status = getConnectivity(model)?.status
  if (connectivityLoading.value && !status) return '확인 중'
  if (status === 'online') return '온라인'
  if (status === 'offline') return '모델 없음'
  if (status === 'error') return '확인 실패'
  if (status === 'skipped') return '비활성'
  return '미확인'
}

function getConnectivityClass(model: LLMModel) {
  const status = getConnectivity(model)?.status
  if (status === 'online') return 'border-emerald-500/20 bg-emerald-500/10 text-emerald-300'
  if (status === 'offline') return 'border-amber-500/20 bg-amber-500/10 text-amber-300'
  if (status === 'error') return 'border-red-500/20 bg-red-500/10 text-red-300'
  if (status === 'skipped') return 'border-zinc-700 bg-zinc-800 text-zinc-500'
  return 'border-zinc-700 bg-zinc-800 text-zinc-400'
}

function getConnectivityTitle(model: LLMModel) {
  const result = getConnectivity(model)
  if (!result) return '아직 연동 상태를 확인하지 않았습니다.'
  const latency = result.latency_ms === null ? '' : ` (${result.latency_ms}ms)`
  return `${result.message}${latency}`
}

async function refreshCredentials() {
  credentials.value = await api.getProviderCredentials()
}

async function openCreateModal() {
  await refreshCredentials()
  selectedModel.value = null
  showModal.value = true
}

async function openEditModal(model: LLMModel) {
  await refreshCredentials()
  selectedModel.value = model
  showModal.value = true
}

function closeModal() {
  showModal.value = false
  selectedModel.value = null
}

async function saveModel(payload: LLMModelPayload) {
  error.value = ''
  try {
    if (selectedModel.value) {
      await api.updateModel(selectedModel.value.id, payload)
    } else {
      await api.createModel(payload)
    }
    closeModal()
    await loadModels()
    await refreshConnectivity()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '모델을 저장하지 못했습니다.'
  }
}

async function disableModel(model: LLMModel) {
  await api.updateModel(model.id, { is_active: false })
  closeModal()
  await loadModels()
  await refreshConnectivity()
}

onMounted(async () => {
  await loadModels()
  await refreshConnectivity()
  window.addEventListener('reload-models', loadModels)
})

onBeforeUnmount(() => {
  window.removeEventListener('reload-models', loadModels)
})
</script>

<template>
  <div class="p-6 lg:p-8">
    <!-- Page header -->
    <div class="mb-6 flex items-center justify-between gap-4">
      <div>
        <p class="mb-1 text-xs font-semibold uppercase tracking-widest text-indigo-400">모델 관리</p>
        <h2 class="text-2xl font-bold text-zinc-100">모델</h2>
      </div>
      <div class="flex flex-wrap items-center gap-2">
        <button
          class="flex items-center gap-2 rounded-lg border border-zinc-700 bg-zinc-900 px-4 py-2.5 text-sm font-semibold text-zinc-200 transition hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-60"
          type="button"
          :disabled="connectivityLoading"
          @click="refreshConnectivity"
        >
          <RefreshCwIcon :class="['h-4 w-4', connectivityLoading ? 'animate-spin' : '']" />
          {{ connectivityLoading ? '연동 확인 중...' : '연동 상태 새로고침' }}
        </button>
        <button
          class="flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-indigo-500/20 transition hover:bg-indigo-500"
          type="button"
          @click="openCreateModal"
        >
          <PlusIcon class="h-4 w-4" />
          모델 추가
        </button>
      </div>
    </div>

    <!-- Filters -->
    <div class="mb-5 flex flex-wrap items-center gap-3">
      <div class="relative min-w-72 flex-1">
        <SearchIcon class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
        <input
          v-model="searchQuery"
          class="w-full rounded-lg border border-zinc-700 bg-zinc-800 py-2.5 pl-9 pr-4 text-sm text-zinc-200 placeholder-zinc-600 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50"
          placeholder="모델명, Provider, 역할 검색..."
          type="text"
        />
      </div>
      <AppSelect
        v-model="statusFilter"
        :options="[{ value: 'all', label: '전체 상태' }, { value: 'active', label: '활성' }, { value: 'inactive', label: '비활성' }]"
      />
    </div>

    <!-- Error -->
    <div v-if="error" class="mb-4 rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2.5 text-sm text-red-400">
      {{ error }}
    </div>
    <div v-if="connectivityError" class="mb-4 rounded-lg border border-amber-500/20 bg-amber-500/10 px-3 py-2.5 text-sm text-amber-300">
      {{ connectivityError }}
    </div>

    <AdminDataTable :loading="loading" :is-empty="filteredModels.length === 0">
      <template #head>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">모델</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">Tier</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">역할</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">품질</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">속도</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">비용</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">토큰 단가($/1M)</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">지연</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">운영 상태</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">연동 상태</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">보안 범위</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">인증 정보</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">상태</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">작업</th>
      </template>

      <template #empty>
        <ServerIcon class="mx-auto mb-4 h-12 w-12 text-zinc-700" />
        <h3 class="mb-1 text-sm font-semibold text-zinc-300">등록된 모델이 없습니다</h3>
        <p class="mb-4 text-sm text-zinc-600">Ollama, OpenAI, Gemini, OpenRouter 모델을 추가해 라우팅을 시작하세요.</p>
        <button
          class="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500"
          @click="openCreateModal"
        >
          모델 추가
        </button>
      </template>

      <tr
        v-for="model in paginatedModels"
        :key="model.id"
        class="table-row cursor-pointer"
        @click="openEditModal(model)"
      >
        <td class="whitespace-nowrap px-5 py-3.5">
          <div class="font-medium text-zinc-200">{{ model.display_name }}</div>
          <div class="text-xs text-zinc-500">{{ model.provider }}/{{ model.name }}</div>
        </td>
        <td class="whitespace-nowrap px-5 py-3.5">
          <span class="rounded-md border border-sky-500/20 bg-sky-500/10 px-2 py-0.5 text-xs font-medium text-sky-300">
            {{ model.model_tier }}
          </span>
        </td>
        <td class="whitespace-nowrap px-5 py-3.5 text-sm text-zinc-300">{{ model.role }}</td>
        <td class="whitespace-nowrap px-5 py-3.5 text-sm text-zinc-300">{{ model.quality_level }}</td>
        <td class="whitespace-nowrap px-5 py-3.5 text-sm text-zinc-300">{{ model.speed_level }}</td>
        <td class="whitespace-nowrap px-5 py-3.5 text-sm text-zinc-300">{{ model.cost_level }}</td>
        <td class="whitespace-nowrap px-5 py-3.5 text-sm text-zinc-300">
          {{ model.input_token_price_per_1m }} / {{ model.output_token_price_per_1m }}
        </td>
        <td class="whitespace-nowrap px-5 py-3.5 text-sm text-zinc-300">
          {{ model.average_latency_ms || '-' }}ms
        </td>
        <td class="whitespace-nowrap px-5 py-3.5">
          <span
            :class="[
              'rounded-md border px-2 py-0.5 text-xs font-medium',
              model.health_status === 'unhealthy'
                ? 'border-red-500/20 bg-red-500/10 text-red-300'
                : 'border-emerald-500/20 bg-emerald-500/10 text-emerald-300'
            ]"
            :title="model.health_reason"
          >
            {{ model.health_status }}
          </span>
        </td>
        <td class="whitespace-nowrap px-5 py-3.5">
          <span
            :class="['rounded-md border px-2 py-0.5 text-xs font-medium', getConnectivityClass(model)]"
            :title="getConnectivityTitle(model)"
          >
            {{ getConnectivityLabel(model) }}
          </span>
        </td>
        <td class="whitespace-nowrap px-5 py-3.5">
          <span class="rounded-md bg-indigo-500/10 px-2 py-0.5 text-xs font-medium text-indigo-400 border border-indigo-500/20">
            {{ model.privacy_level }}
          </span>
        </td>
        <td class="whitespace-nowrap px-5 py-3.5 text-sm text-zinc-400">
          {{ model.provider_credential_display_name || '-' }}
        </td>
        <td class="whitespace-nowrap px-5 py-3.5">
          <span
            :class="[
              'rounded-md px-2 py-0.5 text-xs font-medium border',
              model.is_active
                ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                : 'bg-zinc-800 text-zinc-500 border-zinc-700'
            ]"
          >
            {{ model.is_active ? '활성' : '비활성' }}
          </span>
        </td>
        <td class="whitespace-nowrap px-5 py-3.5">
          <button
            class="rounded-md p-1.5 text-zinc-500 transition-colors hover:bg-zinc-700 hover:text-zinc-200"
            title="수정"
            type="button"
            @click.stop="openEditModal(model)"
          >
            <EditIcon class="h-4 w-4" />
          </button>
        </td>
      </tr>

      <template #footer>
        <PaginationControls
          v-model:page="page"
          v-model:page-size="pageSize"
          :page-size-options="pageSizeOptions"
          :total-items="totalItems"
          :total-pages="totalPages"
          :start-item="startItem"
          :end-item="endItem"
        />
      </template>
    </AdminDataTable>

    <ModelModal
      v-if="showModal"
      :model="selectedModel"
      :credentials="credentials"
      @close="closeModal"
      @disable="disableModel"
      @save="saveModel"
    />
  </div>
</template>
