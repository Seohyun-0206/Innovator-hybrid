<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { CheckCircleIcon, EditIcon, FlaskConicalIcon, ListTreeIcon, PlusIcon, SearchIcon, XCircleIcon } from 'lucide-vue-next'
import AdminDataTable from '../components/common/AdminDataTable.vue'
import AppSelect, { SelectOption } from '../components/common/AppSelect.vue'
import PaginationControls from '../components/common/PaginationControls.vue'
import RoutingRuleModal from '../components/modals/RoutingRuleModal.vue'
import { RoutingPolicy, RoutingRule, RoutingRulePayload, RoutingSimulationResponse, useApi } from '../composables/useApi'
import { usePagination } from '../composables/usePagination'

const api = useApi()
const rules = ref<RoutingRule[]>([])
const policies = ref<RoutingPolicy[]>([])
const selectedRule = ref<RoutingRule | null>(null)
const showModal = ref(false)
const loading = ref(false)
const searchQuery = ref('')
const error = ref('')
const testRule = ref<RoutingRule | null>(null)
const testPrompt = ref('')
const testPolicy = ref('cost-first')
const testResult = ref<RoutingSimulationResponse | null>(null)
const testLoading = ref(false)
const testError = ref('')

const samplePrompts: Record<string, string> = {
  general: '오늘 회의 내용을 세 문장으로 요약해줘.',
  code: 'Django API에서 발생한 stacktrace를 분석하고 해결 방향을 알려줘.',
  reasoning: '복잡한 장애 원인을 단계별로 추론해서 가장 가능성 높은 원인과 검증 절차를 알려줘.',
  long_context: `${'고객 상담 로그와 정책 문서를 종합해서 위반 가능성을 분석해줘.\n'.repeat(80)}`,
  structured_output: '다음 주문 데이터를 JSON 배열로 정리해줘. 필드는 order_id, customer, total_amount, status 로 구성해줘.',
  sensitive: '홍길동의 주민등록번호 900101-1234567 과 이메일 user@example.com 이 포함된 문장을 익명화해줘.',
  always: '이 프롬프트로 항상 매칭되는 라우팅 규칙을 테스트해줘.'
}

const filteredRules = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()
  return rules.value.filter((rule) => {
    return (
      !query ||
      rule.rule_id.toLowerCase().includes(query) ||
      rule.name.toLowerCase().includes(query) ||
      rule.condition_key.toLowerCase().includes(query) ||
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

const policyOptions = computed<SelectOption[]>(() =>
  policies.value.map((policy) => ({ value: policy.name, label: `${policy.display_name} (${policy.name})` }))
)

const matchedTestRule = computed(() =>
  testResult.value?.matched_rules.find((rule) => rule.rule_id === testRule.value?.rule_id) ?? null
)

const topCandidates = computed(() =>
  (testResult.value?.candidates ?? [])
    .filter((candidate) => candidate.rank !== null)
    .sort((a, b) => Number(a.rank) - Number(b.rank))
    .slice(0, 3)
)

const selectedTestCandidate = computed(() =>
  testResult.value?.candidates.find(
    (candidate) =>
      candidate.provider === testResult.value?.selected_provider &&
      candidate.name === testResult.value?.selected_model
  ) ?? null
)

const hasTargetTierCandidate = computed(() =>
  Boolean(testResult.value?.candidates.some((candidate) => candidate.model_tier === testRule.value?.target_tier))
)

const selectedTargetTier = computed(() =>
  Boolean(selectedTestCandidate.value && selectedTestCandidate.value.model_tier === testRule.value?.target_tier)
)

async function loadRules() {
  loading.value = true
  try {
    rules.value = await api.getRoutingRules()
  } finally {
    loading.value = false
  }
}

async function loadPolicies() {
  policies.value = (await api.getPolicies()).filter((policy) => policy.is_active)
  if (!policies.value.some((policy) => policy.name === testPolicy.value) && policies.value[0]) {
    testPolicy.value = policies.value[0].name
  }
}

function openCreateModal() {
  selectedRule.value = null
  showModal.value = true
}

function openEditModal(rule: RoutingRule) {
  selectedRule.value = rule
  showModal.value = true
}

function closeModal() {
  showModal.value = false
  selectedRule.value = null
}

async function saveRule(payload: RoutingRulePayload) {
  error.value = ''
  try {
    if (selectedRule.value) {
      await api.updateRoutingRule(selectedRule.value.id, payload)
    } else {
      await api.createRoutingRule(payload)
    }
    closeModal()
    await loadRules()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to save routing rule'
  }
}

async function deleteRule(rule: RoutingRule) {
  await api.deleteRoutingRule(rule.id)
  closeModal()
  if (testRule.value?.id === rule.id) {
    closeTestPanel()
  }
  await loadRules()
}

function openTestPanel(rule: RoutingRule) {
  testRule.value = rule
  testPrompt.value = samplePrompts[rule.condition_key] ?? samplePrompts.general
  testResult.value = null
  testError.value = ''
}

function closeTestPanel() {
  testRule.value = null
  testPrompt.value = ''
  testResult.value = null
  testError.value = ''
}

async function runRuleTest() {
  if (!testRule.value) {
    return
  }

  testLoading.value = true
  testError.value = ''
  testResult.value = null
  try {
    testResult.value = await api.simulateRouting(testPrompt.value, testPolicy.value)
  } catch (err) {
    testError.value = err instanceof Error ? err.message : 'Failed to test routing rule'
  } finally {
    testLoading.value = false
  }
}

onMounted(async () => {
  await Promise.all([loadRules(), loadPolicies()])
})
</script>

<template>
  <div class="p-6 lg:p-8">
    <div class="mb-6 flex items-center justify-between gap-4">
      <div>
        <p class="mb-1 text-xs font-semibold uppercase tracking-widest text-indigo-400">Rule Based Routing</p>
        <h2 class="text-2xl font-bold text-zinc-100">Routing Rules</h2>
      </div>
      <button
        class="flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-indigo-500/20 transition hover:bg-indigo-500"
        type="button"
        @click="openCreateModal"
      >
        <PlusIcon class="h-4 w-4" />
        Add Rule
      </button>
    </div>

    <div class="mb-5 flex flex-wrap items-center gap-3">
      <div class="relative min-w-72 flex-1">
        <SearchIcon class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
        <input
          v-model="searchQuery"
          class="w-full rounded-lg border border-zinc-700 bg-zinc-800 py-2.5 pl-9 pr-4 text-sm text-zinc-200 placeholder-zinc-600 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50"
          placeholder="Search rule, condition, or tier..."
          type="text"
        />
      </div>
    </div>

    <div v-if="error" class="mb-4 rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2.5 text-sm text-red-400">
      {{ error }}
    </div>

    <section v-if="testRule" class="mb-5 rounded-xl border border-zinc-800 bg-zinc-900 p-5">
      <div class="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p class="mb-1 text-xs font-semibold uppercase tracking-widest text-indigo-400">Rule Test</p>
          <h3 class="text-sm font-semibold text-zinc-100">{{ testRule.rule_id }} · {{ testRule.name }}</h3>
          <p class="mt-1 text-xs text-zinc-500">
            Condition {{ testRule.condition_key }} should prefer {{ testRule.target_tier }} tier when this rule matches.
          </p>
        </div>
        <button
          class="rounded-lg p-1.5 text-zinc-500 transition-colors hover:bg-zinc-800 hover:text-zinc-200"
          title="Close test panel"
          type="button"
          @click="closeTestPanel"
        >
          <XCircleIcon class="h-5 w-5" />
        </button>
      </div>

      <div v-if="!testRule.is_active" class="mb-4 rounded-lg border border-amber-500/20 bg-amber-500/10 px-3 py-2.5 text-sm text-amber-400">
        This rule is inactive, so the simulator will not match it until it is enabled.
      </div>

      <div class="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div class="space-y-4">
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">Test Prompt</span>
            <textarea
              v-model="testPrompt"
              rows="5"
              class="w-full resize-y rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 placeholder-zinc-600 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50"
            ></textarea>
          </label>
          <div class="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto]">
            <label class="block">
              <span class="mb-1.5 block text-xs font-medium text-zinc-400">Policy</span>
              <AppSelect v-model="testPolicy" :options="policyOptions" />
            </label>
            <div class="flex items-end">
              <button
                class="flex h-10 items-center gap-2 rounded-lg bg-indigo-600 px-4 text-sm font-semibold text-white shadow-lg shadow-indigo-500/20 transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-50"
                :disabled="testLoading || !testPrompt.trim() || !testPolicy"
                type="button"
                @click="runRuleTest"
              >
                <div v-if="testLoading" class="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white"></div>
                <FlaskConicalIcon v-else class="h-4 w-4" />
                {{ testLoading ? 'Testing...' : 'Run Test' }}
              </button>
            </div>
          </div>
        </div>

        <aside class="rounded-lg border border-zinc-800 bg-zinc-800/40 p-4">
          <div v-if="testError" class="rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2.5 text-sm text-red-400">
            {{ testError }}
          </div>
          <div v-else-if="testResult" class="space-y-4">
            <div
              :class="[
                'flex items-start gap-2 rounded-lg border px-3 py-2.5 text-sm',
                matchedTestRule
                  ? 'border-emerald-500/20 bg-emerald-500/10 text-emerald-400'
                  : 'border-amber-500/20 bg-amber-500/10 text-amber-400'
              ]"
            >
              <CheckCircleIcon v-if="matchedTestRule" class="mt-0.5 h-4 w-4 shrink-0" />
              <XCircleIcon v-else class="mt-0.5 h-4 w-4 shrink-0" />
              <span>
                {{ matchedTestRule ? 'Rule matched this prompt.' : 'Rule did not match this prompt.' }}
              </span>
            </div>

            <div
              v-if="matchedTestRule && !selectedTargetTier"
              class="rounded-lg border border-amber-500/20 bg-amber-500/10 px-3 py-2.5 text-sm text-amber-400"
            >
              <p class="font-medium">Matched, but target tier was not selected.</p>
              <p class="mt-1 text-xs leading-5 text-amber-300/90">
                {{ hasTargetTierCandidate ? 'A higher ranking rule or policy filter may have changed the final ranking.' : `No active ${testRule.target_tier} tier candidate is available, so the engine fell back to another eligible model.` }}
              </p>
            </div>

            <div>
              <p class="mb-1 text-[10px] font-medium uppercase tracking-wide text-zinc-500">Selected Model</p>
              <p class="break-all text-sm font-semibold text-zinc-200">
                {{ testResult.selected_provider }}/{{ testResult.selected_model }}
              </p>
              <p v-if="selectedTestCandidate" class="mt-1 text-xs text-zinc-500">
                selected tier: {{ selectedTestCandidate.model_tier }}
              </p>
            </div>

            <div>
              <p class="mb-1 text-[10px] font-medium uppercase tracking-wide text-zinc-500">Signals</p>
              <p class="text-sm text-zinc-300">
                {{ [testResult.analysis.is_code && 'code', testResult.analysis.requires_reasoning && 'reasoning', testResult.analysis.has_sensitive_data && 'sensitive', testResult.analysis.is_long_context && 'long', testResult.analysis.is_structured_output && 'structured'].filter(Boolean).join(', ') || 'general' }}
              </p>
            </div>

            <div>
              <p class="mb-1 text-[10px] font-medium uppercase tracking-wide text-zinc-500">Matched Rules</p>
              <div v-if="testResult.matched_rules.length" class="flex flex-wrap gap-1.5">
                <span
                  v-for="rule in testResult.matched_rules"
                  :key="rule.rule_id"
                  :class="[
                    'rounded-md border px-2 py-0.5 text-xs font-medium',
                    rule.rule_id === testRule.rule_id
                      ? 'border-emerald-500/20 bg-emerald-500/10 text-emerald-400'
                      : 'border-zinc-700 bg-zinc-800 text-zinc-400'
                  ]"
                >
                  {{ rule.rule_id }} → {{ rule.target_tier }}
                </span>
              </div>
              <p v-else class="text-sm text-zinc-500">No routing rules matched.</p>
            </div>

            <div>
              <p class="mb-1 text-[10px] font-medium uppercase tracking-wide text-zinc-500">Top Candidates</p>
              <div class="space-y-1.5">
                <div v-for="candidate in topCandidates" :key="`${candidate.provider}/${candidate.name}`" class="rounded-md bg-zinc-900/60 px-2 py-1.5">
                  <p class="truncate text-xs font-semibold text-zinc-200">#{{ candidate.rank }} {{ candidate.display_name }}</p>
                  <p class="truncate text-[11px] text-zinc-500">{{ candidate.model_tier }} · {{ candidate.provider }}/{{ candidate.name }}</p>
                </div>
              </div>
            </div>
          </div>
          <div v-else class="flex min-h-44 flex-col items-center justify-center text-center text-sm text-zinc-500">
            <FlaskConicalIcon class="mb-3 h-8 w-8 text-zinc-700" />
            Run a test to see whether this rule matches and which model is selected.
          </div>
        </aside>
      </div>
    </section>

    <AdminDataTable :loading="loading" :is-empty="filteredRules.length === 0">
      <template #head>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">Rule</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">Condition</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">Target Tier</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">Priority</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">Status</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">Actions</th>
      </template>

      <template #empty>
        <ListTreeIcon class="mx-auto mb-4 h-12 w-12 text-zinc-700" />
        <h3 class="mb-1 text-sm font-semibold text-zinc-300">No routing rules found</h3>
        <p class="mb-4 text-sm text-zinc-600">Create service-specific rules that prefer a model tier.</p>
        <button class="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500" @click="openCreateModal">
          Add Rule
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
        <td class="whitespace-nowrap px-5 py-3.5 text-sm text-zinc-300">{{ rule.condition_key }}</td>
        <td class="whitespace-nowrap px-5 py-3.5">
          <span class="rounded-md border border-sky-500/20 bg-sky-500/10 px-2 py-0.5 text-xs font-medium text-sky-300">
            {{ rule.target_tier }}
          </span>
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
          <button class="mr-1 rounded-md p-1.5 text-zinc-500 transition-colors hover:bg-zinc-700 hover:text-zinc-200" title="Test" type="button" @click.stop="openTestPanel(rule)">
            <FlaskConicalIcon class="h-4 w-4" />
          </button>
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

    <RoutingRuleModal
      v-if="showModal"
      :rule="selectedRule"
      @close="closeModal"
      @delete="deleteRule"
      @save="saveRule"
    />
  </div>
</template>
