<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { CalculatorIcon, SearchIcon, ZapIcon } from 'lucide-vue-next'
import AppSelect, { SelectOption } from '../components/common/AppSelect.vue'
import PaginationControls from '../components/common/PaginationControls.vue'
import { RoutingPolicy, RoutingSimulationResponse, useApi } from '../composables/useApi'
import { usePagination } from '../composables/usePagination'

const api = useApi()
const prompt = ref('Django API에서 발생한 stacktrace를 분석하고 해결 방향을 알려줘.')
const policy = ref('cost-first')
const policies = ref<RoutingPolicy[]>([])
const simulation = ref<RoutingSimulationResponse | null>(null)
const loading = ref(false)
const error = ref('')
const candidateQuery = ref('')

const policyOptions = computed<SelectOption[]>(() =>
  policies.value.map((item) => ({ value: item.name, label: `${item.display_name} (${item.name})` }))
)

const filteredCandidates = computed(() => {
  const query = candidateQuery.value.trim().toLowerCase()
  return (simulation.value?.candidates ?? []).filter((candidate) => {
    if (!query) {
      return true
    }
    return (
      candidate.provider.toLowerCase().includes(query) ||
      candidate.name.toLowerCase().includes(query) ||
      candidate.display_name.toLowerCase().includes(query) ||
      candidate.role.toLowerCase().includes(query)
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
  paginatedItems: paginatedCandidates
} = usePagination(filteredCandidates)

async function runSimulation() {
  loading.value = true
  error.value = ''
  simulation.value = null
  try {
    simulation.value = await api.simulateRouting(prompt.value, policy.value)
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to simulate routing'
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  policies.value = (await api.getPolicies()).filter((item) => item.is_active)
  if (!policies.value.some((item) => item.name === policy.value) && policies.value[0]) {
    policy.value = policies.value[0].name
  }
})
</script>

<template>
  <div class="p-6 lg:p-8">
    <div class="mb-6 flex items-center justify-between gap-4">
      <div>
        <p class="mb-1 text-xs font-semibold uppercase tracking-widest text-indigo-400">라우팅</p>
        <h2 class="text-2xl font-bold text-zinc-100">시뮬레이션</h2>
      </div>
      <button
        class="flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-indigo-500/20 transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-50"
        :disabled="loading || !prompt.trim()"
        type="button"
        @click="runSimulation"
      >
        <div v-if="loading" class="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white"></div>
        <CalculatorIcon v-else class="h-4 w-4" />
        {{ loading ? '시뮬레이션 중...' : '시뮬레이션 실행' }}
      </button>
    </div>

    <div class="mb-6 grid gap-5 lg:grid-cols-[420px_minmax(0,1fr)]">
      <section class="rounded-xl border border-zinc-800 bg-zinc-900 p-5">
        <h3 class="mb-4 text-sm font-semibold text-zinc-200">시나리오</h3>
        <label class="mb-4 block">
          <span class="mb-1.5 block text-xs font-medium text-zinc-400">정책</span>
          <AppSelect v-model="policy" :options="policyOptions" />
        </label>
        <label class="block">
          <span class="mb-1.5 block text-xs font-medium text-zinc-400">프롬프트</span>
          <textarea
            v-model="prompt"
            rows="12"
            class="w-full resize-y rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 placeholder-zinc-600 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50"
          />
        </label>
      </section>

      <section class="rounded-xl border border-zinc-800 bg-zinc-900 p-5">
        <h3 class="mb-4 text-sm font-semibold text-zinc-200">판정 결과</h3>
        <div v-if="error" class="rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2.5 text-sm text-red-400">
          {{ error }}
        </div>
        <div v-else-if="simulation" class="space-y-4">
          <div class="grid gap-3 md:grid-cols-3">
            <div class="rounded-lg bg-zinc-800/60 p-3">
              <p class="mb-1 text-[10px] font-medium uppercase tracking-wide text-zinc-500">선택 모델</p>
              <p class="truncate text-sm font-semibold text-zinc-200">{{ simulation.selected_provider }}/{{ simulation.selected_model }}</p>
            </div>
            <div class="rounded-lg bg-zinc-800/60 p-3">
              <p class="mb-1 text-[10px] font-medium uppercase tracking-wide text-zinc-500">토큰</p>
              <p class="text-sm font-semibold text-zinc-200">{{ simulation.analysis.estimated_tokens }}</p>
            </div>
            <div class="rounded-lg bg-zinc-800/60 p-3">
              <p class="mb-1 text-[10px] font-medium uppercase tracking-wide text-zinc-500">분석 신호</p>
              <p class="text-sm font-semibold text-zinc-200">
                {{ [simulation.analysis.is_code && 'code', simulation.analysis.requires_reasoning && 'reasoning', simulation.analysis.has_sensitive_data && 'sensitive', simulation.analysis.is_long_context && 'long'].filter(Boolean).join(', ') || 'general' }}
              </p>
            </div>
          </div>
          <div>
            <div class="mb-1.5 flex items-center gap-1.5">
              <ZapIcon class="h-3.5 w-3.5 text-amber-400" />
              <p class="text-xs font-semibold uppercase tracking-wide text-zinc-400">사유</p>
            </div>
            <p class="text-sm leading-relaxed text-zinc-300">{{ simulation.routing_reason }}</p>
          </div>
        </div>
        <div v-else class="flex min-h-56 flex-col items-center justify-center text-center">
          <CalculatorIcon class="mb-3 h-8 w-8 text-zinc-700" />
          <p class="text-sm text-zinc-500">LLM을 호출하지 않고 모델 순위를 시뮬레이션합니다.</p>
        </div>
      </section>
    </div>

    <section class="rounded-xl border border-zinc-800 bg-zinc-900">
      <div class="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-800 px-5 py-4">
        <h3 class="text-sm font-semibold text-zinc-200">후보 모델 점수</h3>
        <div class="relative min-w-72">
          <SearchIcon class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
          <input
            v-model="candidateQuery"
            class="w-full rounded-lg border border-zinc-700 bg-zinc-800 py-2 pl-9 pr-4 text-sm text-zinc-200 placeholder-zinc-600 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50"
            placeholder="후보 모델 검색..."
            type="text"
          />
        </div>
      </div>

      <div class="overflow-x-auto">
        <table class="min-w-full divide-y divide-zinc-800/60">
          <thead class="bg-zinc-900">
            <tr>
              <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">순위</th>
              <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">모델</th>
              <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">역할</th>
              <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">점수</th>
              <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">Est. Cost</th>
              <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">Latency</th>
              <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">Breakdown</th>
              <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">사유</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-zinc-800/60">
            <tr v-if="!simulation">
              <td colspan="8" class="px-5 py-12 text-center text-sm text-zinc-500">No simulation result yet.</td>
            </tr>
            <tr
              v-for="candidate in paginatedCandidates"
              :key="`${candidate.provider}/${candidate.name}`"
              :class="candidate.eligible ? 'table-row cursor-pointer' : 'opacity-50'"
            >
              <td class="whitespace-nowrap px-5 py-3.5 text-sm font-semibold text-zinc-300">
                {{ candidate.rank ? `#${candidate.rank}` : '-' }}
              </td>
              <td class="whitespace-nowrap px-5 py-3.5">
                <div class="font-medium text-zinc-200">{{ candidate.display_name }}</div>
                <div class="text-xs text-zinc-500">{{ candidate.provider }}/{{ candidate.name }}</div>
              </td>
              <td class="whitespace-nowrap px-5 py-3.5 text-sm text-zinc-300">{{ candidate.role }}</td>
              <td class="whitespace-nowrap px-5 py-3.5 text-sm font-semibold text-zinc-200">{{ candidate.score }}</td>
              <td class="whitespace-nowrap px-5 py-3.5 text-sm text-zinc-300">
                ${{ Number(candidate.estimated_total_cost_usd).toFixed(6) }}
                <div class="text-xs text-zinc-500">in {{ candidate.input_token_price_per_1m }} / out {{ candidate.output_token_price_per_1m }}</div>
              </td>
              <td class="whitespace-nowrap px-5 py-3.5 text-sm text-zinc-300">
                {{ candidate.average_latency_ms || '-' }}ms
                <div class="text-xs text-zinc-500">{{ candidate.timeout_seconds }}s timeout</div>
              </td>
              <td class="whitespace-nowrap px-5 py-3.5 text-xs text-zinc-400">
                Q {{ candidate.score_breakdown.quality }} / S {{ candidate.score_breakdown.speed }} / C {{ candidate.score_breakdown.cost }} / CTX {{ candidate.score_breakdown.context }} / P {{ candidate.score_breakdown.privacy }}
              </td>
              <td class="min-w-72 px-5 py-3.5 text-sm text-zinc-400">{{ candidate.reasons.join('; ') }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <PaginationControls
        v-if="simulation && filteredCandidates.length"
        v-model:page="page"
        v-model:page-size="pageSize"
        :page-size-options="pageSizeOptions"
        :total-items="totalItems"
        :total-pages="totalPages"
        :start-item="startItem"
        :end-item="endItem"
      />
    </section>
  </div>
</template>
