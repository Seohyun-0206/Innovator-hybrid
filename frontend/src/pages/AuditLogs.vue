<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { FileClockIcon, SearchIcon } from 'lucide-vue-next'
import AdminDataTable from '../components/common/AdminDataTable.vue'
import PaginationControls from '../components/common/PaginationControls.vue'
import { AuditLog, useApi } from '../composables/useApi'
import { usePagination } from '../composables/usePagination'

const api = useApi()
const logs = ref<AuditLog[]>([])
const loading = ref(false)
const searchQuery = ref('')

const filteredLogs = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()
  return logs.value.filter((log) => {
    return (
      !query ||
      (log.actor_username ?? 'system').toLowerCase().includes(query) ||
      log.action.toLowerCase().includes(query) ||
      log.resource_type.toLowerCase().includes(query) ||
      log.resource_name.toLowerCase().includes(query) ||
      (log.ip_address ?? '').toLowerCase().includes(query)
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
  paginatedItems: paginatedLogs
} = usePagination(filteredLogs)

async function loadLogs() {
  loading.value = true
  try {
    logs.value = await api.getAuditLogs()
  } finally {
    loading.value = false
  }
}

function formatDate(value: string) {
  return new Date(value).toLocaleString()
}

onMounted(loadLogs)
</script>

<template>
  <div class="p-6 lg:p-8">
    <div class="mb-6">
      <p class="mb-1 text-xs font-semibold uppercase tracking-widest text-indigo-400">시스템 관리</p>
      <h2 class="text-2xl font-bold text-zinc-100">감사 로그</h2>
    </div>

    <div class="mb-5 flex flex-wrap items-center gap-3">
      <div class="relative min-w-72 flex-1">
        <SearchIcon class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
        <input
          v-model="searchQuery"
          class="w-full rounded-lg border border-zinc-700 bg-zinc-800 py-2.5 pl-9 pr-4 text-sm text-zinc-200 placeholder-zinc-600 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50"
          placeholder="수행자, 작업, 리소스, IP 검색..."
          type="text"
        />
      </div>
    </div>

    <AdminDataTable :loading="loading" :is-empty="filteredLogs.length === 0">
      <template #head>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">작업</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">수행자</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">리소스</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">IP</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">생성 시각</th>
      </template>

      <template #empty>
        <FileClockIcon class="mx-auto mb-4 h-12 w-12 text-zinc-700" />
        <h3 class="mb-1 text-sm font-semibold text-zinc-300">감사 로그가 없습니다</h3>
        <p class="text-sm text-zinc-600">보안 및 관리 작업 변경 이력이 여기에 표시됩니다.</p>
      </template>

      <tr v-for="log in paginatedLogs" :key="log.id" class="table-row">
        <td class="whitespace-nowrap px-5 py-3.5">
          <div class="font-medium text-zinc-200">{{ log.action }}</div>
          <div class="text-xs text-zinc-500">{{ log.resource_type }}</div>
        </td>
        <td class="whitespace-nowrap px-5 py-3.5 text-sm text-zinc-400">{{ log.actor_username || 'system' }}</td>
        <td class="px-5 py-3.5 text-sm text-zinc-400">
          <div class="truncate">{{ log.resource_name || '-' }}</div>
          <div class="text-xs text-zinc-500">{{ log.resource_id || '-' }}</div>
        </td>
        <td class="whitespace-nowrap px-5 py-3.5 text-sm text-zinc-400">{{ log.ip_address || '-' }}</td>
        <td class="whitespace-nowrap px-5 py-3.5 text-sm text-zinc-400">{{ formatDate(log.created_at) }}</td>
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
  </div>
</template>
