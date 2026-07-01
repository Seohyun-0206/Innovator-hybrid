<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { DownloadIcon, EditIcon, KeyRoundIcon, PlusIcon, SearchIcon } from 'lucide-vue-next'
import AdminDataTable from '../components/common/AdminDataTable.vue'
import PaginationControls from '../components/common/PaginationControls.vue'
import ProviderCredentialModal from '../components/modals/ProviderCredentialModal.vue'
import ProviderModelSyncModal from '../components/modals/ProviderModelSyncModal.vue'
import { ProviderCredential, ProviderCredentialPayload, ProviderModelCandidate, useApi } from '../composables/useApi'
import { usePagination } from '../composables/usePagination'

const api = useApi()
const credentials = ref<ProviderCredential[]>([])
const selectedCredential = ref<ProviderCredential | null>(null)
const syncCredential = ref<ProviderCredential | null>(null)
const providerModels = ref<ProviderModelCandidate[]>([])
const showModal = ref(false)
const showSyncModal = ref(false)
const loading = ref(false)
const syncLoading = ref(false)
const importing = ref(false)
const searchQuery = ref('')
const error = ref('')

const filteredCredentials = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()
  return credentials.value.filter((credential) => {
    return (
      !query ||
      credential.provider.toLowerCase().includes(query) ||
      credential.display_name.toLowerCase().includes(query) ||
      credential.base_url.toLowerCase().includes(query)
    )
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
  paginatedItems: paginatedCredentials
} = usePagination(filteredCredentials)

function formatDate(value: string | null) {
  return value ? new Date(value).toLocaleString() : '-'
}

async function loadCredentials() {
  loading.value = true
  try {
    credentials.value = await api.getProviderCredentials()
  } finally {
    loading.value = false
  }
}

function openCreateModal() {
  selectedCredential.value = null
  showModal.value = true
}

function openEditModal(credential: ProviderCredential) {
  selectedCredential.value = credential
  showModal.value = true
}

function closeModal() {
  showModal.value = false
  selectedCredential.value = null
}

async function saveCredential(payload: ProviderCredentialPayload) {
  error.value = ''
  try {
    if (selectedCredential.value) {
      await api.updateProviderCredential(selectedCredential.value.id, payload)
    } else {
      await api.createProviderCredential(payload)
    }
    closeModal()
    await loadCredentials()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '인증 정보를 저장하지 못했습니다.'
  }
}

async function deleteCredential(credential: ProviderCredential) {
  await api.deleteProviderCredential(credential.id)
  closeModal()
  await loadCredentials()
}

async function openSyncModal(credential: ProviderCredential) {
  error.value = ''
  syncCredential.value = credential
  showSyncModal.value = true
  await refreshProviderModels()
}

function closeSyncModal() {
  showSyncModal.value = false
  syncCredential.value = null
  providerModels.value = []
}

async function refreshProviderModels() {
  if (!syncCredential.value) {
    return
  }
  syncLoading.value = true
  try {
    const response = await api.previewProviderModels(syncCredential.value.id)
    providerModels.value = response.models
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Provider 모델 목록을 가져오지 못했습니다.'
  } finally {
    syncLoading.value = false
  }
}

async function importProviderModels(modelNames: string[]) {
  if (!syncCredential.value) {
    return
  }
  importing.value = true
  error.value = ''
  try {
    await api.importProviderModels(syncCredential.value.id, modelNames)
    // 가져온 모델을 로컬 목록에서 '등록됨'으로 표시 (OpenAI 재호출 없이)
    const importedSet = new Set(modelNames)
    providerModels.value = providerModels.value.map((m) =>
      importedSet.has(m.name) ? { ...m, exists: true } : m
    )
    // 모델 탭이 이미 열려 있으면 목록 자동 갱신
    window.dispatchEvent(new CustomEvent('reload-models'))
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Provider 모델을 가져오지 못했습니다.'
  } finally {
    importing.value = false
  }
}

onMounted(loadCredentials)
</script>

<template>
  <div class="p-6 lg:p-8">
    <div class="mb-6 flex items-center justify-between gap-4">
      <div>
        <p class="mb-1 text-xs font-semibold uppercase tracking-widest text-indigo-400">모델 관리</p>
        <h2 class="text-2xl font-bold text-zinc-100">인증 관리</h2>
      </div>
      <button
        class="flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-indigo-500/20 transition hover:bg-indigo-500"
        type="button"
        @click="openCreateModal"
      >
        <PlusIcon class="h-4 w-4" />
        인증 정보 추가
      </button>
    </div>

    <div class="mb-5 flex flex-wrap items-center gap-3">
      <div class="relative min-w-72 flex-1">
        <SearchIcon class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
        <input
          v-model="searchQuery"
          class="w-full rounded-lg border border-zinc-700 bg-zinc-800 py-2.5 pl-9 pr-4 text-sm text-zinc-200 placeholder-zinc-600 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50"
          placeholder="Provider, 이름, URL 검색..."
          type="text"
        />
      </div>
    </div>

    <div v-if="error" class="mb-4 rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2.5 text-sm text-red-400">
      {{ error }}
    </div>

    <AdminDataTable :loading="loading" :is-empty="filteredCredentials.length === 0">
      <template #head>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">Provider</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">Base URL</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">접근 토큰</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">사용 이력</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">상태</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">작업</th>
      </template>

      <template #empty>
        <KeyRoundIcon class="mx-auto mb-4 h-12 w-12 text-zinc-700" />
        <h3 class="mb-1 text-sm font-semibold text-zinc-300">등록된 인증 정보가 없습니다</h3>
        <p class="mb-4 text-sm text-zinc-600">Ollama, OpenAI, Gemini, OpenRouter 인증 정보를 추가해 외부 모델 라우팅을 사용할 수 있습니다.</p>
        <button
          class="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500"
          @click="openCreateModal"
        >
          인증 정보 추가
        </button>
      </template>

      <tr
        v-for="credential in paginatedCredentials"
        :key="credential.id"
        class="table-row cursor-pointer"
        @click="openEditModal(credential)"
      >
        <td class="whitespace-nowrap px-5 py-3.5">
          <div class="font-medium text-zinc-200">{{ credential.display_name }}</div>
          <div class="text-xs text-zinc-500">{{ credential.provider }}</div>
        </td>
        <td class="px-5 py-3.5 text-sm text-zinc-400">{{ credential.base_url }}</td>
        <td class="whitespace-nowrap px-5 py-3.5 font-mono text-sm text-zinc-500">{{ credential.access_token_masked || '-' }}</td>
        <td class="whitespace-nowrap px-5 py-3.5 text-sm text-zinc-400">
          <div>최근 사용 {{ formatDate(credential.last_used_at) }}</div>
          <div class="text-xs text-zinc-500">토큰 교체 {{ formatDate(credential.token_rotated_at) }}</div>
        </td>
        <td class="whitespace-nowrap px-5 py-3.5">
          <span
            :class="[
              'rounded-md px-2 py-0.5 text-xs font-medium border',
              credential.is_active
                ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                : 'bg-zinc-800 text-zinc-500 border-zinc-700'
            ]"
          >
            {{ credential.is_active ? '활성' : '비활성' }}
          </span>
        </td>
        <td class="whitespace-nowrap px-5 py-3.5">
          <button
            class="mr-1 rounded-md p-1.5 text-zinc-500 transition-colors hover:bg-zinc-700 hover:text-zinc-200 disabled:cursor-not-allowed disabled:opacity-40"
            title="Provider 모델 동기화"
            type="button"
            :disabled="!credential.is_active"
            @click.stop="openSyncModal(credential)"
          >
            <DownloadIcon class="h-4 w-4" />
          </button>
          <button
            class="rounded-md p-1.5 text-zinc-500 transition-colors hover:bg-zinc-700 hover:text-zinc-200"
            title="수정"
            type="button"
            @click.stop="openEditModal(credential)"
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

    <ProviderCredentialModal
      v-if="showModal"
      :credential="selectedCredential"
      @close="closeModal"
      @delete="deleteCredential"
      @save="saveCredential"
    />

    <ProviderModelSyncModal
      v-if="showSyncModal && syncCredential"
      :credential="syncCredential"
      :models="providerModels"
      :loading="syncLoading"
      :importing="importing"
      @close="closeSyncModal"
      @refresh="refreshProviderModels"
      @import="importProviderModels"
    />
  </div>
</template>
