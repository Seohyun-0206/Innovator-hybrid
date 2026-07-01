<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { EditIcon, PlusIcon, SearchIcon, SlidersHorizontalIcon } from 'lucide-vue-next'
import AdminDataTable from '../components/common/AdminDataTable.vue'
import PaginationControls from '../components/common/PaginationControls.vue'
import ThresholdRuleModal from '../components/modals/ThresholdRuleModal.vue'
import { ThresholdRule, ThresholdRulePayload, useApi } from '../composables/useApi'
import { usePagination } from '../composables/usePagination'

const api = useApi()
const rules = ref<ThresholdRule[]>([])
const selectedRule = ref<ThresholdRule | null>(null)
const showModal = ref(false)
const loading = ref(false)
const searchQuery = ref('')
const error = ref('')

const filteredRules = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()
  return rules.value.filter((rule) => {
    return (
      !query ||
      rule.rule_id.toLowerCase().includes(query) ||
      rule.name.toLowerCase().includes(query) ||
      rule.metric_key.toLowerCase().includes(query) ||
      rule.target_tier.toLowerCase().includes(query)
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
  paginatedItems: paginatedRules
} = usePagination(filteredRules)

async function loadRules() {
  loading.value = true
  try {
    rules.value = await api.getThresholdRules()
  } finally {
    loading.value = false
  }
}

function openCreateModal() {
  selectedRule.value = null
  showModal.value = true
}

function openEditModal(rule: ThresholdRule) {
  selectedRule.value = rule
  showModal.value = true
}

function closeModal() {
  showModal.value = false
  selectedRule.value = null
}

async function saveRule(payload: ThresholdRulePayload) {
  error.value = ''
  try {
    if (selectedRule.value) {
      await api.updateThresholdRule(selectedRule.value.id, payload)
    } else {
      await api.createThresholdRule(payload)
    }
    closeModal()
    await loadRules()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to save threshold rule'
  }
}

async function deleteRule(rule: ThresholdRule) {
  await api.deleteThresholdRule(rule.id)
  closeModal()
  await loadRules()
}

onMounted(loadRules)
</script>

<template>
  <div class="p-6 lg:p-8">
    <div class="mb-6 flex items-center justify-between gap-4">
      <div>
        <p class="mb-1 text-xs font-semibold uppercase tracking-widest text-indigo-400">Policy Conditions</p>
        <h2 class="text-2xl font-bold text-zinc-100">Threshold Rules</h2>
      </div>
      <button
        class="flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-indigo-500/20 transition hover:bg-indigo-500"
        type="button"
        @click="openCreateModal"
      >
        <PlusIcon class="h-4 w-4" />
        Add Threshold
      </button>
    </div>

    <div class="mb-5 flex flex-wrap items-center gap-3">
      <div class="relative min-w-72 flex-1">
        <SearchIcon class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
        <input
          v-model="searchQuery"
          class="w-full rounded-lg border border-zinc-700 bg-zinc-800 py-2.5 pl-9 pr-4 text-sm text-zinc-200 placeholder-zinc-600 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50"
          placeholder="Search threshold, metric, or tier..."
          type="text"
        />
      </div>
    </div>

    <div v-if="error" class="mb-4 rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2.5 text-sm text-red-400">
      {{ error }}
    </div>

    <AdminDataTable :loading="loading" :is-empty="filteredRules.length === 0">
      <template #head>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">Rule</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">Metric</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">Threshold</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">Action</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">Priority</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">Status</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">Edit</th>
      </template>

      <template #empty>
        <SlidersHorizontalIcon class="mx-auto mb-4 h-12 w-12 text-zinc-700" />
        <h3 class="mb-1 text-sm font-semibold text-zinc-300">No threshold rules found</h3>
        <p class="mb-4 text-sm text-zinc-600">Create token, latency, timeout, or validation thresholds.</p>
        <button class="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500" @click="openCreateModal">
          Add Threshold
        </button>
      </template>

      <tr
        v-for="rule in paginatedRules"
        :key="rule.id"
        class="table-row cursor-pointer"
        @click="openEditModal(rule)"
      >
        <td class="whitespace-nowrap px-5 py-3.5">
          <div class="font-medium text-zinc-200">{{ rule.rule_id }} · {{ rule.name }}</div>
          <div class="max-w-lg truncate text-xs text-zinc-500">{{ rule.description || '-' }}</div>
        </td>
        <td class="whitespace-nowrap px-5 py-3.5 text-sm text-zinc-300">{{ rule.metric_key }}</td>
        <td class="whitespace-nowrap px-5 py-3.5 text-sm text-zinc-300">{{ rule.operator }} {{ rule.threshold_value }}</td>
        <td class="whitespace-nowrap px-5 py-3.5 text-sm text-zinc-300">
          <div>{{ rule.action_on_trigger }}</div>
          <div class="text-xs text-zinc-500">{{ rule.target_tier || (rule.max_tokens ? `${rule.max_tokens} max tokens` : '-') }}</div>
        </td>
        <td class="whitespace-nowrap px-5 py-3.5 text-sm text-zinc-300">{{ rule.priority }}</td>
        <td class="whitespace-nowrap px-5 py-3.5">
          <span
            :class="[
              'rounded-md px-2 py-0.5 text-xs font-medium border',
              rule.is_active
                ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                : 'bg-zinc-800 text-zinc-500 border-zinc-700'
            ]"
          >
            {{ rule.is_active ? 'active' : 'inactive' }}
          </span>
        </td>
        <td class="whitespace-nowrap px-5 py-3.5">
          <button class="rounded-md p-1.5 text-zinc-500 transition-colors hover:bg-zinc-700 hover:text-zinc-200" title="Edit" type="button" @click.stop="openEditModal(rule)">
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

    <ThresholdRuleModal
      v-if="showModal"
      :rule="selectedRule"
      @close="closeModal"
      @delete="deleteRule"
      @save="saveRule"
    />
  </div>
</template>
