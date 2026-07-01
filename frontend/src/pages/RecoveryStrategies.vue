<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { EditIcon, PlusIcon, RepeatIcon, SearchIcon } from 'lucide-vue-next'
import AdminDataTable from '../components/common/AdminDataTable.vue'
import PaginationControls from '../components/common/PaginationControls.vue'
import RecoveryStrategyModal from '../components/modals/RecoveryStrategyModal.vue'
import { RecoveryStrategy, RecoveryStrategyPayload, useApi } from '../composables/useApi'
import { usePagination } from '../composables/usePagination'

const api = useApi()
const strategies = ref<RecoveryStrategy[]>([])
const selectedStrategy = ref<RecoveryStrategy | null>(null)
const showModal = ref(false)
const loading = ref(false)
const searchQuery = ref('')
const error = ref('')

const filteredStrategies = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()
  return strategies.value.filter((strategy) => {
    return (
      !query ||
      strategy.strategy_id.toLowerCase().includes(query) ||
      strategy.name.toLowerCase().includes(query) ||
      strategy.trigger_event.toLowerCase().includes(query) ||
      strategy.action.toLowerCase().includes(query)
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
  paginatedItems: paginatedStrategies
} = usePagination(filteredStrategies)

async function loadStrategies() {
  loading.value = true
  try {
    strategies.value = await api.getRecoveryStrategies()
  } finally {
    loading.value = false
  }
}

function openCreateModal() {
  selectedStrategy.value = null
  showModal.value = true
}

function openEditModal(strategy: RecoveryStrategy) {
  selectedStrategy.value = strategy
  showModal.value = true
}

function closeModal() {
  showModal.value = false
  selectedStrategy.value = null
}

async function saveStrategy(payload: RecoveryStrategyPayload) {
  error.value = ''
  try {
    if (selectedStrategy.value) {
      await api.updateRecoveryStrategy(selectedStrategy.value.id, payload)
    } else {
      await api.createRecoveryStrategy(payload)
    }
    closeModal()
    await loadStrategies()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '복구 전략을 저장하지 못했습니다.'
  }
}

async function deleteStrategy(strategy: RecoveryStrategy) {
  await api.deleteRecoveryStrategy(strategy.id)
  closeModal()
  await loadStrategies()
}

onMounted(loadStrategies)
</script>

<template>
  <div class="p-6 lg:p-8">
    <div class="mb-6 flex items-center justify-between gap-4">
      <div>
        <p class="mb-1 text-xs font-semibold uppercase tracking-widest text-indigo-400">검증·복구 정책</p>
        <h2 class="text-2xl font-bold text-zinc-100">복구 전략</h2>
      </div>
      <button
        class="flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-indigo-500/20 transition hover:bg-indigo-500"
        type="button"
        @click="openCreateModal"
      >
        <PlusIcon class="h-4 w-4" />
        복구 전략 추가
      </button>
    </div>

    <div class="mb-5 flex flex-wrap items-center gap-3">
      <div class="relative min-w-72 flex-1">
        <SearchIcon class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
        <input
          v-model="searchQuery"
          class="w-full rounded-lg border border-zinc-700 bg-zinc-800 py-2.5 pl-9 pr-4 text-sm text-zinc-200 placeholder-zinc-600 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50"
          placeholder="전략명, 트리거, 조치 검색..."
          type="text"
        />
      </div>
    </div>

    <div v-if="error" class="mb-4 rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2.5 text-sm text-red-400">
      {{ error }}
    </div>

    <AdminDataTable :loading="loading" :is-empty="filteredStrategies.length === 0">
      <template #head>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">전략</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">트리거</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">조치</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">상태</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">수정</th>
      </template>

      <template #empty>
        <RepeatIcon class="mx-auto mb-4 h-12 w-12 text-zinc-700" />
        <h3 class="mb-1 text-sm font-semibold text-zinc-300">등록된 복구 전략이 없습니다</h3>
        <p class="mb-4 text-sm text-zinc-600">재시도, fallback, escalation에 재사용할 복구 전략을 생성하세요.</p>
        <button class="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500" @click="openCreateModal">
          복구 전략 추가
        </button>
      </template>

      <tr
        v-for="strategy in paginatedStrategies"
        :key="strategy.id"
        class="table-row cursor-pointer"
        @click="openEditModal(strategy)"
      >
        <td class="whitespace-nowrap px-5 py-3.5">
          <div class="font-medium text-zinc-200">{{ strategy.strategy_id }} · {{ strategy.name }}</div>
          <div class="max-w-lg truncate text-xs text-zinc-500">{{ strategy.description || '-' }}</div>
        </td>
        <td class="whitespace-nowrap px-5 py-3.5 text-sm text-zinc-300">{{ strategy.trigger_event }}</td>
        <td class="whitespace-nowrap px-5 py-3.5 text-sm text-zinc-300">
          <div>{{ strategy.action }}</div>
          <div class="text-xs text-zinc-500">{{ strategy.max_retries }}회 재시도 · {{ strategy.target_tier || '-' }}</div>
        </td>
        <td class="whitespace-nowrap px-5 py-3.5">
          <span
            :class="[
              'rounded-md px-2 py-0.5 text-xs font-medium border',
              strategy.is_active
                ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                : 'bg-zinc-800 text-zinc-500 border-zinc-700'
            ]"
          >
            {{ strategy.is_active ? '활성' : '비활성' }}
          </span>
        </td>
        <td class="whitespace-nowrap px-5 py-3.5">
          <button class="rounded-md p-1.5 text-zinc-500 transition-colors hover:bg-zinc-700 hover:text-zinc-200" title="수정" type="button" @click.stop="openEditModal(strategy)">
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

    <RecoveryStrategyModal
      v-if="showModal"
      :strategy="selectedStrategy"
      @close="closeModal"
      @delete="deleteStrategy"
      @save="saveStrategy"
    />
  </div>
</template>
