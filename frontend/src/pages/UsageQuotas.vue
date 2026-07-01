<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { EditIcon, GaugeIcon, PlusIcon, SearchIcon } from 'lucide-vue-next'
import AdminDataTable from '../components/common/AdminDataTable.vue'
import PaginationControls from '../components/common/PaginationControls.vue'
import UsageQuotaModal from '../components/modals/UsageQuotaModal.vue'
import { AppUser, UsageQuota, UsageQuotaPayload, useApi } from '../composables/useApi'
import { usePagination } from '../composables/usePagination'

const api = useApi()
const quotas = ref<UsageQuota[]>([])
const users = ref<AppUser[]>([])
const selectedQuota = ref<UsageQuota | null>(null)
const showModal = ref(false)
const loading = ref(false)
const searchQuery = ref('')
const error = ref('')

const filteredQuotas = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()
  return quotas.value.filter((quota) => {
    return (
      !query ||
      quota.name.toLowerCase().includes(query) ||
      quota.provider.toLowerCase().includes(query) ||
      (quota.username ?? 'all users').toLowerCase().includes(query)
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
  paginatedItems: paginatedQuotas
} = usePagination(filteredQuotas)

async function loadPageData() {
  loading.value = true
  try {
    const [loadedQuotas, loadedUsers] = await Promise.all([api.getUsageQuotas(), api.getUsers()])
    quotas.value = loadedQuotas
    users.value = loadedUsers
  } finally {
    loading.value = false
  }
}

function providerLabel(provider: string) {
  return provider || '전체 Provider'
}

function getActionLabel(action: string) {
  if (action === 'block') return '요청 차단'
  if (action === 'local_fallback') return '로컬 fallback'
  return action
}

function formatUsd(value: string | number | null) {
  return `$${Number(value || 0).toFixed(6)}`
}

function formatPercent(value: number | null) {
  return value === null ? '-' : `${Math.round(value * 100)}%`
}

function openCreateModal() {
  selectedQuota.value = null
  showModal.value = true
}

function openEditModal(quota: UsageQuota) {
  selectedQuota.value = quota
  showModal.value = true
}

function closeModal() {
  showModal.value = false
  selectedQuota.value = null
}

async function saveQuota(payload: UsageQuotaPayload) {
  error.value = ''
  try {
    if (selectedQuota.value) {
      await api.updateUsageQuota(selectedQuota.value.id, payload)
    } else {
      await api.createUsageQuota(payload)
    }
    closeModal()
    await loadPageData()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '사용량 한도를 저장하지 못했습니다.'
  }
}

async function deleteQuota(quota: UsageQuota) {
  await api.deleteUsageQuota(quota.id)
  closeModal()
  await loadPageData()
}

onMounted(loadPageData)
</script>

<template>
  <div class="p-6 lg:p-8">
    <div class="mb-6 flex items-center justify-between gap-4">
      <div>
        <p class="mb-1 text-xs font-semibold uppercase tracking-widest text-indigo-400">운영 모니터링</p>
        <h2 class="text-2xl font-bold text-zinc-100">사용량 한도</h2>
      </div>
      <button
        class="flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-indigo-500/20 transition hover:bg-indigo-500"
        type="button"
        @click="openCreateModal"
      >
        <PlusIcon class="h-4 w-4" />
        한도 추가
      </button>
    </div>

    <div class="mb-5 flex flex-wrap items-center gap-3">
      <div class="relative min-w-72 flex-1">
        <SearchIcon class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
        <input
          v-model="searchQuery"
          class="w-full rounded-lg border border-zinc-700 bg-zinc-800 py-2.5 pl-9 pr-4 text-sm text-zinc-200 placeholder-zinc-600 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50"
          placeholder="한도명, 사용자, Provider 검색..."
          type="text"
        />
      </div>
    </div>

    <div v-if="error" class="mb-4 rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2.5 text-sm text-red-400">
      {{ error }}
    </div>

    <AdminDataTable :loading="loading" :is-empty="filteredQuotas.length === 0">
      <template #head>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">한도</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">범위</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">제한</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">이번 달</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">초과 시 조치</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">상태</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">수정</th>
      </template>

      <template #empty>
        <GaugeIcon class="mx-auto mb-4 h-12 w-12 text-zinc-700" />
        <h3 class="mb-1 text-sm font-semibold text-zinc-300">등록된 사용량 한도가 없습니다</h3>
        <p class="mb-4 text-sm text-zinc-600">사용자와 Provider별 요청 수 또는 비용 한도를 생성하세요.</p>
        <button class="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500" @click="openCreateModal">
          한도 추가
        </button>
      </template>

      <tr
        v-for="quota in paginatedQuotas"
        :key="quota.id"
        class="table-row cursor-pointer"
        @click="openEditModal(quota)"
      >
        <td class="whitespace-nowrap px-5 py-3.5">
          <div class="font-medium text-zinc-200">{{ quota.name }}</div>
          <div class="text-xs text-zinc-500">{{ quota.action_on_exceed === 'block' ? '초과 시 차단' : '로컬 fallback 시도' }}</div>
        </td>
        <td class="whitespace-nowrap px-5 py-3.5 text-sm text-zinc-400">
          {{ quota.username || '전체 사용자' }} · {{ providerLabel(quota.provider) }}
        </td>
        <td class="whitespace-nowrap px-5 py-3.5 text-sm text-zinc-300">
          <div>{{ quota.monthly_request_limit ?? '-' }}건 / 월</div>
          <div class="text-xs text-zinc-500">${{ quota.monthly_cost_limit_usd ?? '-' }} / 월</div>
        </td>
        <td class="min-w-56 px-5 py-3.5 text-sm text-zinc-300">
          <div class="mb-2">
            <div class="mb-1 flex items-center justify-between gap-3 text-xs">
              <span class="text-zinc-400">{{ quota.current_month_requests }}건</span>
              <span class="text-zinc-500">{{ formatPercent(quota.request_usage_ratio) }}</span>
            </div>
            <div class="h-1.5 overflow-hidden rounded-full bg-zinc-800">
              <div
                class="h-full rounded-full bg-indigo-500"
                :style="{ width: `${Math.round((quota.request_usage_ratio ?? 0) * 100)}%` }"
              ></div>
            </div>
          </div>
          <div>
            <div class="mb-1 flex items-center justify-between gap-3 text-xs">
              <span class="text-zinc-400">{{ formatUsd(quota.current_month_cost_usd) }}</span>
              <span class="text-zinc-500">{{ formatPercent(quota.cost_usage_ratio) }}</span>
            </div>
            <div class="h-1.5 overflow-hidden rounded-full bg-zinc-800">
              <div
                class="h-full rounded-full bg-emerald-500"
                :style="{ width: `${Math.round((quota.cost_usage_ratio ?? 0) * 100)}%` }"
              ></div>
            </div>
          </div>
        </td>
        <td class="whitespace-nowrap px-5 py-3.5 text-sm text-zinc-400">{{ getActionLabel(quota.action_on_exceed) }}</td>
        <td class="whitespace-nowrap px-5 py-3.5">
          <span
            :class="[
              'rounded-md px-2 py-0.5 text-xs font-medium border',
              quota.is_exceeded
                ? 'bg-red-500/10 text-red-400 border-red-500/20'
                : quota.is_active
                  ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                : 'bg-zinc-800 text-zinc-500 border-zinc-700'
            ]"
          >
            {{ quota.is_exceeded ? '초과' : quota.is_active ? '활성' : '비활성' }}
          </span>
        </td>
        <td class="whitespace-nowrap px-5 py-3.5">
          <button class="rounded-md p-1.5 text-zinc-500 transition-colors hover:bg-zinc-700 hover:text-zinc-200" title="수정" type="button" @click.stop="openEditModal(quota)">
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

    <UsageQuotaModal
      v-if="showModal"
      :quota="selectedQuota"
      :users="users"
      @close="closeModal"
      @delete="deleteQuota"
      @save="saveQuota"
    />
  </div>
</template>
