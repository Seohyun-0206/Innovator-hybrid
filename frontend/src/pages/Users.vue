<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { EditIcon, PlusIcon, SearchIcon, UsersIcon } from 'lucide-vue-next'
import AdminDataTable from '../components/common/AdminDataTable.vue'
import PaginationControls from '../components/common/PaginationControls.vue'
import UserModal from '../components/modals/UserModal.vue'
import { AppUser, AppUserPayload, ScreenDefinition, useApi } from '../composables/useApi'
import { usePagination } from '../composables/usePagination'

const api = useApi()
const users = ref<AppUser[]>([])
const screens = ref<ScreenDefinition[]>([])
const selectedUser = ref<AppUser | null>(null)
const showModal = ref(false)
const loading = ref(false)
const searchQuery = ref('')
const error = ref('')

const filteredUsers = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()
  return users.value.filter((user) => !query || user.username.toLowerCase().includes(query))
})
const {
  page,
  pageSize,
  pageSizeOptions,
  totalItems,
  totalPages,
  startItem,
  endItem,
  paginatedItems: paginatedUsers
} = usePagination(filteredUsers)

async function loadPageData() {
  loading.value = true
  try {
    const [loadedUsers, loadedScreens] = await Promise.all([api.getUsers(), api.getScreens()])
    users.value = loadedUsers
    screens.value = loadedScreens
  } finally {
    loading.value = false
  }
}

async function openCreateModal() {
  selectedUser.value = null
  showModal.value = true
}

async function openEditModal(user: AppUser) {
  selectedUser.value = user
  showModal.value = true
}

function closeModal() {
  showModal.value = false
  selectedUser.value = null
}

async function saveUser(payload: AppUserPayload) {
  error.value = ''
  try {
    const cleanPayload = { ...payload }
    if (selectedUser.value && !cleanPayload.password) {
      delete cleanPayload.password
    }
    if (selectedUser.value) {
      await api.updateUser(selectedUser.value.id, cleanPayload)
    } else {
      await api.createUser(cleanPayload)
    }
    closeModal()
    await loadPageData()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to save user'
  }
}

async function deleteUser(user: AppUser) {
  await api.deleteUser(user.id)
  closeModal()
  await loadPageData()
}

onMounted(loadPageData)
</script>

<template>
  <div class="p-6 lg:p-8">
    <div class="mb-6 flex items-center justify-between gap-4">
      <div>
        <p class="mb-1 text-xs font-semibold uppercase tracking-widest text-indigo-400">시스템 관리</p>
        <h2 class="text-2xl font-bold text-zinc-100">사용자</h2>
      </div>
      <button
        class="flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-indigo-500/20 transition hover:bg-indigo-500"
        type="button"
        @click="openCreateModal"
      >
        <PlusIcon class="h-4 w-4" />
        사용자 추가
      </button>
    </div>

    <div class="mb-5 flex flex-wrap items-center gap-3">
      <div class="relative min-w-72 flex-1">
        <SearchIcon class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
        <input
          v-model="searchQuery"
          class="w-full rounded-lg border border-zinc-700 bg-zinc-800 py-2.5 pl-9 pr-4 text-sm text-zinc-200 placeholder-zinc-600 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50"
          placeholder="사용자명 검색..."
          type="text"
        />
      </div>
    </div>

    <div v-if="error" class="mb-4 rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2.5 text-sm text-red-400">
      {{ error }}
    </div>

    <AdminDataTable :loading="loading" :is-empty="filteredUsers.length === 0">
      <template #head>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">사용자명</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">관리자</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">상태</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">화면 권한</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">작업</th>
      </template>

      <template #empty>
        <UsersIcon class="mx-auto mb-4 h-12 w-12 text-zinc-700" />
        <h3 class="mb-1 text-sm font-semibold text-zinc-300">등록된 사용자가 없습니다</h3>
        <button
          class="mt-3 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500"
          @click="openCreateModal"
        >
          사용자 추가
        </button>
      </template>

      <tr
        v-for="user in paginatedUsers"
        :key="user.id"
        class="table-row cursor-pointer"
        @click="openEditModal(user)"
      >
        <td class="whitespace-nowrap px-5 py-3.5 font-medium text-zinc-200">{{ user.username }}</td>
        <td class="whitespace-nowrap px-5 py-3.5">
          <span :class="['rounded-md px-2 py-0.5 text-xs font-medium border', user.is_staff ? 'bg-amber-500/10 text-amber-400 border-amber-500/20' : 'bg-zinc-800 text-zinc-500 border-zinc-700']">
            {{ user.is_staff ? '예' : '아니오' }}
          </span>
        </td>
        <td class="whitespace-nowrap px-5 py-3.5">
          <span :class="['rounded-md px-2 py-0.5 text-xs font-medium border', user.is_active ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 'bg-zinc-800 text-zinc-500 border-zinc-700']">
            {{ user.is_active ? '활성' : '비활성' }}
          </span>
        </td>
        <td class="px-5 py-3.5 text-sm text-zinc-500">{{ user.allowed_screens.join(', ') }}</td>
        <td class="whitespace-nowrap px-5 py-3.5">
          <button
            class="rounded-md p-1.5 text-zinc-500 transition-colors hover:bg-zinc-700 hover:text-zinc-200"
            title="수정"
            type="button"
            @click.stop="openEditModal(user)"
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

    <UserModal v-if="showModal" :user="selectedUser" :screens="screens" @close="closeModal" @delete="deleteUser" @save="saveUser" />
  </div>
</template>
