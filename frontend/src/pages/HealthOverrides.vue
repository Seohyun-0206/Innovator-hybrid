<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { EditIcon, HeartPulseIcon, PlusIcon, SearchIcon } from 'lucide-vue-next'
import AdminDataTable from '../components/common/AdminDataTable.vue'
import PaginationControls from '../components/common/PaginationControls.vue'
import ModelHealthOverrideModal from '../components/modals/ModelHealthOverrideModal.vue'
import { ModelHealthOverride, ModelHealthOverridePayload, useApi } from '../composables/useApi'
import { usePagination } from '../composables/usePagination'

const api = useApi()
const overrides = ref<ModelHealthOverride[]>([])
const selectedOverride = ref<ModelHealthOverride | null>(null)
const showModal = ref(false)
const loading = ref(false)
const searchQuery = ref('')
const error = ref('')

const filteredOverrides = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()
  return overrides.value.filter((override) => {
    return (
      !query ||
      override.name.toLowerCase().includes(query) ||
      override.provider.toLowerCase().includes(query) ||
      override.model_name.toLowerCase().includes(query) ||
      override.reason.toLowerCase().includes(query)
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
  paginatedItems: paginatedOverrides
} = usePagination(filteredOverrides)

async function loadOverrides() {
  loading.value = true
  try {
    overrides.value = await api.getModelHealthOverrides()
  } finally {
    loading.value = false
  }
}

function providerLabel(provider: string) {
  return provider || 'all providers'
}

function modelLabel(modelName: string) {
  return modelName || 'all models'
}

function formatDate(value: string | null) {
  return value ? new Date(value).toLocaleString() : 'no expiry'
}

function isExpired(value: string | null) {
  return Boolean(value && new Date(value).getTime() <= Date.now())
}

function openCreateModal() {
  selectedOverride.value = null
  showModal.value = true
}

function openEditModal(override: ModelHealthOverride) {
  selectedOverride.value = override
  showModal.value = true
}

function closeModal() {
  showModal.value = false
  selectedOverride.value = null
}

async function saveOverride(payload: ModelHealthOverridePayload) {
  error.value = ''
  try {
    if (selectedOverride.value) {
      await api.updateModelHealthOverride(selectedOverride.value.id, payload)
    } else {
      await api.createModelHealthOverride(payload)
    }
    closeModal()
    await loadOverrides()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '수동 조치를 저장하지 못했습니다.'
  }
}

async function deleteOverride(override: ModelHealthOverride) {
  await api.deleteModelHealthOverride(override.id)
  closeModal()
  await loadOverrides()
}

onMounted(loadOverrides)
</script>

<template>
  <div class="p-6 lg:p-8">
    <div class="mb-6 flex items-center justify-between gap-4">
      <div>
        <p class="mb-1 text-xs font-semibold uppercase tracking-widest text-indigo-400">운영 모니터링</p>
        <h2 class="text-2xl font-bold text-zinc-100">수동 조치</h2>
      </div>
      <button
        class="flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-indigo-500/20 transition hover:bg-indigo-500"
        type="button"
        @click="openCreateModal"
      >
        <PlusIcon class="h-4 w-4" />
        수동 조치 추가
      </button>
    </div>

    <div class="mb-5 flex flex-wrap items-center gap-3">
      <div class="relative min-w-72 flex-1">
        <SearchIcon class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
        <input
          v-model="searchQuery"
          class="w-full rounded-lg border border-zinc-700 bg-zinc-800 py-2.5 pl-9 pr-4 text-sm text-zinc-200 placeholder-zinc-600 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50"
          placeholder="조치명, Provider, 모델, 사유 검색..."
          type="text"
        />
      </div>
    </div>

    <div v-if="error" class="mb-4 rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2.5 text-sm text-red-400">
      {{ error }}
    </div>

    <AdminDataTable :loading="loading" :is-empty="filteredOverrides.length === 0">
      <template #head>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">수동 조치</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">범위</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">사유</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">만료</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">상태</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">수정</th>
      </template>

      <template #empty>
        <HeartPulseIcon class="mx-auto mb-4 h-12 w-12 text-zinc-700" />
        <h3 class="mb-1 text-sm font-semibold text-zinc-300">등록된 수동 조치가 없습니다</h3>
        <p class="mb-4 text-sm text-zinc-600">라우팅 모델을 임시로 정상 처리하거나 차단하는 조치를 생성하세요.</p>
        <button class="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500" @click="openCreateModal">
          수동 조치 추가
        </button>
      </template>

      <tr
        v-for="override in paginatedOverrides"
        :key="override.id"
        class="table-row cursor-pointer"
        @click="openEditModal(override)"
      >
        <td class="whitespace-nowrap px-5 py-3.5">
          <div class="font-medium text-zinc-200">{{ override.name }}</div>
          <div class="text-xs text-zinc-500">{{ override.override_type === 'force_healthy' ? '정상 강제 처리' : '비정상 강제 처리' }}</div>
        </td>
        <td class="whitespace-nowrap px-5 py-3.5 text-sm text-zinc-400">
          {{ providerLabel(override.provider) }} · {{ modelLabel(override.model_name) }}
        </td>
        <td class="max-w-sm px-5 py-3.5 text-sm text-zinc-400">
          <span class="block truncate">{{ override.reason || '-' }}</span>
          <span class="text-xs text-zinc-500">작성자 {{ override.created_by_username || '-' }}</span>
        </td>
        <td class="whitespace-nowrap px-5 py-3.5 text-sm text-zinc-400">
          {{ formatDate(override.expires_at) }}
        </td>
        <td class="whitespace-nowrap px-5 py-3.5">
          <span
            :class="[
              'rounded-md px-2 py-0.5 text-xs font-medium border',
              override.is_active && !isExpired(override.expires_at)
                ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                : 'bg-zinc-800 text-zinc-500 border-zinc-700'
            ]"
          >
            {{ override.is_active && !isExpired(override.expires_at) ? '활성' : '비활성' }}
          </span>
        </td>
        <td class="whitespace-nowrap px-5 py-3.5">
          <button class="rounded-md p-1.5 text-zinc-500 transition-colors hover:bg-zinc-700 hover:text-zinc-200" title="수정" type="button" @click.stop="openEditModal(override)">
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

    <ModelHealthOverrideModal
      v-if="showModal"
      :override="selectedOverride"
      @close="closeModal"
      @delete="deleteOverride"
      @save="saveOverride"
    />
  </div>
</template>
