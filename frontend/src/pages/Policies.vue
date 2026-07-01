<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { EditIcon, PlusIcon, RouteIcon, SearchIcon } from 'lucide-vue-next'
import AdminDataTable from '../components/common/AdminDataTable.vue'
import PaginationControls from '../components/common/PaginationControls.vue'
import PolicyModal from '../components/modals/PolicyModal.vue'
import AppSelect from '../components/common/AppSelect.vue'
import { RoutingPolicy, RoutingPolicyPayload, useApi } from '../composables/useApi'
import { usePagination } from '../composables/usePagination'

const api = useApi()
const policies = ref<RoutingPolicy[]>([])
const selectedPolicy = ref<RoutingPolicy | null>(null)
const showModal = ref(false)
const loading = ref(false)
const searchQuery = ref('')
const statusFilter = ref<'all' | 'active' | 'inactive'>('all')
const error = ref('')

const filteredPolicies = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()
  return policies.value.filter((policy) => {
    const matchesQuery =
      !query ||
      policy.name.toLowerCase().includes(query) ||
      policy.display_name.toLowerCase().includes(query) ||
      policy.description.toLowerCase().includes(query)
    const matchesStatus =
      statusFilter.value === 'all' ||
      (statusFilter.value === 'active' && policy.is_active) ||
      (statusFilter.value === 'inactive' && !policy.is_active)
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
  paginatedItems: paginatedPolicies
} = usePagination(filteredPolicies)

async function loadPolicies() {
  loading.value = true
  try {
    policies.value = await api.getPolicies()
  } finally {
    loading.value = false
  }
}

function openCreateModal() {
  selectedPolicy.value = null
  showModal.value = true
}

function openEditModal(policy: RoutingPolicy) {
  selectedPolicy.value = policy
  showModal.value = true
}

function closeModal() {
  showModal.value = false
  selectedPolicy.value = null
}

async function savePolicy(payload: RoutingPolicyPayload) {
  error.value = ''
  try {
    if (selectedPolicy.value) {
      await api.updatePolicy(selectedPolicy.value.id, payload)
    } else {
      await api.createPolicy(payload)
    }
    closeModal()
    await loadPolicies()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to save policy'
  }
}

async function disablePolicy(policy: RoutingPolicy) {
  await api.updatePolicy(policy.id, { is_active: false })
  closeModal()
  await loadPolicies()
}

onMounted(loadPolicies)
</script>

<template>
  <div class="p-6 lg:p-8">
    <div class="mb-6 flex items-center justify-between gap-4">
      <div>
        <p class="mb-1 text-xs font-semibold uppercase tracking-widest text-indigo-400">정책 설계</p>
        <h2 class="text-2xl font-bold text-zinc-100">정책</h2>
      </div>
      <button
        class="flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-indigo-500/20 transition hover:bg-indigo-500"
        type="button"
        @click="openCreateModal"
      >
        <PlusIcon class="h-4 w-4" />
        정책 추가
      </button>
    </div>

    <div class="mb-5 flex flex-wrap items-center gap-3">
      <div class="relative min-w-72 flex-1">
        <SearchIcon class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
        <input
          v-model="searchQuery"
          class="w-full rounded-lg border border-zinc-700 bg-zinc-800 py-2.5 pl-9 pr-4 text-sm text-zinc-200 placeholder-zinc-600 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50"
          placeholder="정책명 또는 설명 검색..."
          type="text"
        />
      </div>
      <AppSelect
        v-model="statusFilter"
        :options="[{ value: 'all', label: '전체 상태' }, { value: 'active', label: '활성' }, { value: 'inactive', label: '비활성' }]"
      />
    </div>

    <div v-if="error" class="mb-4 rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2.5 text-sm text-red-400">
      {{ error }}
    </div>

    <AdminDataTable :loading="loading" :is-empty="filteredPolicies.length === 0">
      <template #head>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">정책</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">품질</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">속도</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">비용</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">컨텍스트</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">규칙</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">로컬 전용</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">상태</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">작업</th>
      </template>

      <template #empty>
        <RouteIcon class="mx-auto mb-4 h-12 w-12 text-zinc-700" />
        <h3 class="mb-1 text-sm font-semibold text-zinc-300">등록된 정책이 없습니다</h3>
        <p class="mb-4 text-sm text-zinc-600">라우팅 정책을 생성한 뒤 테스트 화면에서 사용할 수 있습니다.</p>
        <button
          class="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500"
          @click="openCreateModal"
        >
          정책 추가
        </button>
      </template>

      <tr
        v-for="policy in paginatedPolicies"
        :key="policy.id"
        class="table-row cursor-pointer"
        @click="openEditModal(policy)"
      >
        <td class="px-5 py-3.5">
          <div class="font-medium text-zinc-200">{{ policy.display_name }}</div>
          <div class="text-xs text-zinc-500">{{ policy.name }}</div>
        </td>
        <td class="whitespace-nowrap px-5 py-3.5 text-sm text-zinc-300">{{ policy.priority_config.quality_weight ?? '기본값' }}</td>
        <td class="whitespace-nowrap px-5 py-3.5 text-sm text-zinc-300">{{ policy.priority_config.speed_weight ?? '기본값' }}</td>
        <td class="whitespace-nowrap px-5 py-3.5 text-sm text-zinc-300">{{ policy.priority_config.cost_weight ?? '기본값' }}</td>
        <td class="whitespace-nowrap px-5 py-3.5 text-sm text-zinc-300">{{ policy.priority_config.context_weight ?? '기본값' }}</td>
        <td class="px-5 py-3.5 text-xs text-zinc-400">
          <div class="flex max-w-80 flex-wrap gap-1.5">
            <span v-if="policy.priority_config.prefer_coding_models ?? true" class="rounded border border-zinc-700 bg-zinc-800 px-2 py-0.5">code</span>
            <span v-if="policy.priority_config.prefer_reasoning_models ?? true" class="rounded border border-zinc-700 bg-zinc-800 px-2 py-0.5">reasoning</span>
            <span v-if="policy.priority_config.min_context_window" class="rounded border border-zinc-700 bg-zinc-800 px-2 py-0.5">ctx {{ policy.priority_config.min_context_window }}+</span>
            <span v-if="policy.priority_config.max_estimated_cost_usd" class="rounded border border-zinc-700 bg-zinc-800 px-2 py-0.5">max ${{ policy.priority_config.max_estimated_cost_usd }}</span>
            <span v-if="policy.priority_config.fallback_to_local_on_budget" class="rounded border border-zinc-700 bg-zinc-800 px-2 py-0.5">budget local fallback</span>
          </div>
        </td>
        <td class="whitespace-nowrap px-5 py-3.5">
          <span
            :class="[
              'rounded-md px-2 py-0.5 text-xs font-medium border',
              policy.priority_config.local_only
                ? 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20'
                : 'bg-zinc-800 text-zinc-500 border-zinc-700'
            ]"
          >
            {{ policy.priority_config.local_only ? 'yes' : 'no' }}
          </span>
        </td>
        <td class="whitespace-nowrap px-5 py-3.5">
          <span
            :class="[
              'rounded-md px-2 py-0.5 text-xs font-medium border',
              policy.is_active
                ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                : 'bg-zinc-800 text-zinc-500 border-zinc-700'
            ]"
          >
            {{ policy.is_active ? '활성' : '비활성' }}
          </span>
        </td>
        <td class="whitespace-nowrap px-5 py-3.5">
          <button
            class="rounded-md p-1.5 text-zinc-500 transition-colors hover:bg-zinc-700 hover:text-zinc-200"
            title="수정"
            type="button"
            @click.stop="openEditModal(policy)"
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

    <PolicyModal
      v-if="showModal"
      :policy="selectedPolicy"
      @close="closeModal"
      @disable="disablePolicy"
      @save="savePolicy"
    />
  </div>
</template>
