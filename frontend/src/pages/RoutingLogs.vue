<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { SearchIcon } from 'lucide-vue-next'
import { RoutingLog, useApi } from '../composables/useApi'
import PaginationControls from '../components/common/PaginationControls.vue'
import RoutingLogDetailModal from '../components/modals/RoutingLogDetailModal.vue'

type LogDensity = 'comfortable' | 'compact' | 'dense'

const DENSITY_KEY = 'routing-logs-density'
const api = useApi()
const logs = ref<RoutingLog[]>([])
const selectedLog = ref<RoutingLog | null>(null)
const loading = ref(true)
const searchQuery = ref('')
const page = ref(1)
const pageSize = ref(10)
const pageSizeOptions = [10, 25, 50, 100]
const totalItems = ref(0)
const totalPages = computed(() => Math.max(1, Math.ceil(totalItems.value / pageSize.value)))
const startItem = computed(() => (totalItems.value === 0 ? 0 : (page.value - 1) * pageSize.value + 1))
const endItem = computed(() => Math.min(page.value * pageSize.value, totalItems.value))
const density = ref<LogDensity>((localStorage.getItem(DENSITY_KEY) as LogDensity) || 'comfortable')

const densityClasses = computed(() => {
  if (density.value === 'dense') {
    return {
      cell: 'px-3 py-2 text-xs',
      badge: 'rounded bg-zinc-800 px-1.5 py-0.5 text-[10px] font-medium text-zinc-300'
    }
  }

  if (density.value === 'compact') {
    return {
      cell: 'px-4 py-2.5 text-xs',
      badge: 'rounded-md bg-zinc-800 px-2 py-0.5 text-[11px] font-medium text-zinc-300'
    }
  }

  return {
    cell: 'px-5 py-3.5 text-sm',
    badge: 'rounded-md bg-zinc-800 px-2 py-0.5 text-xs font-medium text-zinc-300'
  }
})

watch(density, (value) => {
  localStorage.setItem(DENSITY_KEY, value)
})

let searchTimer: number | undefined

async function loadLogs() {
  loading.value = true
  try {
    const response = await api.getLogs({
      page: page.value,
      pageSize: pageSize.value,
      search: searchQuery.value.trim(),
      ordering: '-created_at'
    })
    logs.value = response.results
    totalItems.value = response.count
  } finally {
    loading.value = false
  }
}

function openLogDetail(log: RoutingLog) {
  selectedLog.value = log
}

function closeLogDetail() {
  selectedLog.value = null
}

watch(page, loadLogs)

watch(pageSize, () => {
  if (page.value === 1) {
    void loadLogs()
  } else {
    page.value = 1
  }
})

watch(searchQuery, () => {
  window.clearTimeout(searchTimer)
  searchTimer = window.setTimeout(() => {
    if (page.value === 1) {
      void loadLogs()
    } else {
      page.value = 1
    }
  }, 300)
})

onMounted(loadLogs)
</script>

<template>
  <div class="p-6 lg:p-8">
    <!-- Page header -->
    <div class="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <p class="mb-1 text-xs font-semibold uppercase tracking-widest text-indigo-400">운영 모니터링</p>
        <h2 class="text-2xl font-bold text-zinc-100">라우팅 로그</h2>
      </div>

      <div class="flex flex-wrap items-center gap-3">
        <div class="relative w-72">
          <SearchIcon class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
          <input
            v-model="searchQuery"
            class="w-full rounded-lg border border-zinc-700 bg-zinc-800 py-2 pl-9 pr-3 text-sm text-zinc-200 placeholder-zinc-600 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50"
            placeholder="로그 검색..."
            type="text"
          />
        </div>

        <label class="flex items-center gap-2 text-sm text-zinc-500">
          밀도
          <select
            v-model="density"
            class="rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-sm text-zinc-200 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50"
          >
            <option value="comfortable">여유</option>
            <option value="compact">보통</option>
            <option value="dense">촘촘</option>
          </select>
        </label>
      </div>
    </div>

    <div class="rounded-xl border border-zinc-800 bg-zinc-900">
      <div v-if="loading" class="flex items-center justify-center py-16 gap-3 text-zinc-500">
        <div class="h-4 w-4 animate-spin rounded-full border-2 border-zinc-700 border-t-indigo-500"></div>
        <span class="text-sm">로그를 불러오는 중...</span>
      </div>

      <div v-else class="overflow-x-auto">
        <table class="min-w-full">
          <thead>
            <tr class="border-b border-zinc-800">
              <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">프롬프트</th>
              <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">정책</th>
              <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">모델</th>
              <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">지연</th>
              <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">사유</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-zinc-800/60">
            <tr
              v-for="log in logs"
              :key="log.id"
              class="table-row cursor-pointer"
              @click="openLogDetail(log)"
            >
              <td :class="['max-w-xs truncate text-zinc-300', densityClasses.cell]">{{ log.prompt_summary }}</td>
              <td :class="['whitespace-nowrap', densityClasses.cell]">
                <span :class="densityClasses.badge">{{ log.policy }}</span>
              </td>
              <td :class="['whitespace-nowrap text-zinc-400', densityClasses.cell]">{{ log.selected_provider }}/{{ log.selected_model }}</td>
              <td :class="['whitespace-nowrap text-zinc-400', densityClasses.cell]">{{ log.latency_ms }}ms</td>
              <td :class="['max-w-xs truncate text-zinc-500', densityClasses.cell]">{{ log.routing_reason }}</td>
            </tr>
            <tr v-if="!logs.length">
              <td colspan="5" class="px-5 py-16 text-center text-sm text-zinc-600">
                {{ searchQuery.trim() ? '검색 조건에 맞는 로그가 없습니다' : '아직 라우팅 로그가 없습니다' }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <PaginationControls
        v-if="!loading && totalItems"
        v-model:page="page"
        v-model:page-size="pageSize"
        :page-size-options="pageSizeOptions"
        :total-items="totalItems"
        :total-pages="totalPages"
        :start-item="startItem"
        :end-item="endItem"
      />
    </div>

    <RoutingLogDetailModal v-if="selectedLog" :log="selectedLog" @close="closeLogDetail" />
  </div>
</template>
