<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { LogOutIcon, SearchIcon, ShieldIcon } from 'lucide-vue-next'
import AdminDataTable from '../components/common/AdminDataTable.vue'
import PaginationControls from '../components/common/PaginationControls.vue'
import { UserSession, useApi } from '../composables/useApi'
import { usePagination } from '../composables/usePagination'

const api = useApi()
const sessions = ref<UserSession[]>([])
const loading = ref(false)
const searchQuery = ref('')
const error = ref('')

const filteredSessions = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()
  return sessions.value.filter((session) => {
    return (
      !query ||
      session.username.toLowerCase().includes(query) ||
      (session.ip_address ?? '').toLowerCase().includes(query) ||
      session.user_agent.toLowerCase().includes(query) ||
      session.status.toLowerCase().includes(query)
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
  paginatedItems: paginatedSessions
} = usePagination(filteredSessions)

async function loadSessions() {
  loading.value = true
  try {
    sessions.value = await api.getUserSessions()
  } finally {
    loading.value = false
  }
}

async function revokeSession(session: UserSession) {
  error.value = ''
  try {
    await api.revokeUserSession(session.id)
    await loadSessions()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '세션을 종료하지 못했습니다.'
  }
}

function formatDate(value: string | null) {
  return value ? new Date(value).toLocaleString() : '-'
}

function getSessionStatusLabel(session: UserSession) {
  if (session.is_expired && session.status === 'active') return '만료'
  if (session.status === 'active') return '활성'
  if (session.status === 'revoked') return '종료'
  return session.status
}

onMounted(loadSessions)
</script>

<template>
  <div class="p-6 lg:p-8">
    <div class="mb-6 flex items-center justify-between gap-4">
      <div>
        <p class="mb-1 text-xs font-semibold uppercase tracking-widest text-indigo-400">시스템 관리</p>
        <h2 class="text-2xl font-bold text-zinc-100">사용자 세션</h2>
      </div>
    </div>

    <div class="mb-5 flex flex-wrap items-center gap-3">
      <div class="relative min-w-72 flex-1">
        <SearchIcon class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
        <input
          v-model="searchQuery"
          class="w-full rounded-lg border border-zinc-700 bg-zinc-800 py-2.5 pl-9 pr-4 text-sm text-zinc-200 placeholder-zinc-600 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50"
          placeholder="사용자, IP, 브라우저, 상태 검색..."
          type="text"
        />
      </div>
    </div>

    <div v-if="error" class="mb-4 rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2.5 text-sm text-red-400">
      {{ error }}
    </div>

    <AdminDataTable :loading="loading" :is-empty="filteredSessions.length === 0">
      <template #head>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">사용자</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">IP</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">User Agent</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">마지막 접속</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">만료</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">상태</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">작업</th>
      </template>

      <template #empty>
        <ShieldIcon class="mx-auto mb-4 h-12 w-12 text-zinc-700" />
        <h3 class="mb-1 text-sm font-semibold text-zinc-300">세션이 없습니다</h3>
        <p class="text-sm text-zinc-600">관리형 로그인 세션이 여기에 표시됩니다.</p>
      </template>

      <tr v-for="session in paginatedSessions" :key="session.id" class="table-row">
        <td class="whitespace-nowrap px-5 py-3.5">
          <div class="font-medium text-zinc-200">{{ session.username }}</div>
          <div class="text-xs text-zinc-500">{{ formatDate(session.login_at) }}</div>
        </td>
        <td class="whitespace-nowrap px-5 py-3.5 text-sm text-zinc-400">{{ session.ip_address || '-' }}</td>
        <td class="max-w-md px-5 py-3.5 text-sm text-zinc-400">
          <span class="block truncate" :title="session.user_agent">{{ session.user_agent || '-' }}</span>
        </td>
        <td class="whitespace-nowrap px-5 py-3.5 text-sm text-zinc-400">{{ formatDate(session.last_seen_at) }}</td>
        <td class="whitespace-nowrap px-5 py-3.5 text-sm text-zinc-400">{{ formatDate(session.expires_at) }}</td>
        <td class="whitespace-nowrap px-5 py-3.5">
          <span
            :class="[
              'rounded-md border px-2 py-0.5 text-xs font-medium',
              session.status === 'active' && !session.is_expired
                ? 'border-emerald-500/20 bg-emerald-500/10 text-emerald-300'
                : 'border-zinc-700 bg-zinc-800 text-zinc-500'
            ]"
          >
            {{ getSessionStatusLabel(session) }}
          </span>
        </td>
        <td class="whitespace-nowrap px-5 py-3.5">
          <button
            class="rounded-md p-1.5 text-zinc-500 transition-colors hover:bg-zinc-700 hover:text-zinc-200 disabled:cursor-not-allowed disabled:opacity-40"
            title="세션 종료"
            type="button"
            :disabled="session.status !== 'active'"
            @click="revokeSession(session)"
          >
            <LogOutIcon class="h-4 w-4" />
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
  </div>
</template>
