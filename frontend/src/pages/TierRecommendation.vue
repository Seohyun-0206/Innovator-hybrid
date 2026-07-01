<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { LayersIcon, SearchIcon } from 'lucide-vue-next'
import AdminDataTable from '../components/common/AdminDataTable.vue'
import { TierRecommendation, useApi } from '../composables/useApi'

const api = useApi()
const recommendations = ref<TierRecommendation[]>([])
const loading = ref(false)
const searchQuery = ref('')

const TIER_COLORS: Record<string, string> = {
  lightweight: 'border-emerald-500/20 bg-emerald-500/10 text-emerald-400',
  standard: 'border-sky-500/20 bg-sky-500/10 text-sky-300',
  advanced: 'border-violet-500/20 bg-violet-500/10 text-violet-400',
  long_context: 'border-amber-500/20 bg-amber-500/10 text-amber-400',
  structured: 'border-rose-500/20 bg-rose-500/10 text-rose-400',
}

const filtered = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  return recommendations.value.filter(
    (r) => !q || r.display_name.toLowerCase().includes(q) || r.provider.toLowerCase().includes(q) || r.suggested_tier.includes(q)
  )
})

async function load() {
  loading.value = true
  try {
    recommendations.value = await api.getTierRecommendations()
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="p-6 lg:p-8">
    <div class="mb-6 flex items-start justify-between gap-4">
      <div>
        <p class="mb-1 text-xs font-semibold uppercase tracking-widest text-indigo-400">모델 평가</p>
        <h2 class="text-2xl font-bold text-zinc-100">Tier 추천</h2>
        <p class="mt-1 text-sm text-zinc-500">모델 메타데이터(품질, 속도, 비용, 컨텍스트, 역할)를 기반으로 적합한 Tier를 추천합니다.</p>
      </div>
    </div>

    <div class="mb-5 flex flex-wrap items-center gap-3">
      <div class="relative min-w-72 flex-1">
        <SearchIcon class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
        <input
          v-model="searchQuery"
          class="w-full rounded-lg border border-zinc-700 bg-zinc-800 py-2.5 pl-9 pr-4 text-sm text-zinc-200 placeholder-zinc-600 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50"
          placeholder="모델명, Provider, Tier 검색..."
          type="text"
        />
      </div>
    </div>

    <AdminDataTable :loading="loading" :is-empty="filtered.length === 0">
      <template #head>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">모델</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">역할</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">보안 범위</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">컨텍스트</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">품질 / 속도 / 비용</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">현재 Tier</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">추천 Tier</th>
        <th class="px-5 py-3.5 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">추천 사유</th>
      </template>

      <template #empty>
        <LayersIcon class="mx-auto mb-4 h-12 w-12 text-zinc-700" />
        <h3 class="mb-1 text-sm font-semibold text-zinc-300">활성 모델이 없습니다</h3>
        <p class="text-sm text-zinc-600">모델 화면에서 모델을 등록하세요.</p>
      </template>

      <tr v-for="rec in filtered" :key="rec.model_id" class="table-row">
        <td class="px-5 py-3.5">
          <p class="font-medium text-zinc-200">{{ rec.display_name }}</p>
          <p class="text-xs text-zinc-500">{{ rec.provider }}/{{ rec.name }}</p>
        </td>
        <td class="whitespace-nowrap px-5 py-3.5">
          <span class="rounded-md border border-zinc-700 bg-zinc-800 px-2 py-0.5 text-xs text-zinc-400">{{ rec.role }}</span>
        </td>
        <td class="whitespace-nowrap px-5 py-3.5">
          <span :class="[
            'rounded-md border px-2 py-0.5 text-xs font-medium',
            rec.privacy_level === 'local'
              ? 'border-emerald-500/20 bg-emerald-500/10 text-emerald-400'
              : 'border-amber-500/20 bg-amber-500/10 text-amber-400'
          ]">{{ rec.privacy_level }}</span>
        </td>
        <td class="whitespace-nowrap px-5 py-3.5 text-sm text-zinc-300">{{ rec.context_window.toLocaleString() }}</td>
        <td class="whitespace-nowrap px-5 py-3.5 text-sm text-zinc-400">{{ rec.quality_level }} / {{ rec.speed_level }} / {{ rec.cost_level }}</td>
        <td class="whitespace-nowrap px-5 py-3.5">
          <span class="rounded-md border border-zinc-700 bg-zinc-800/60 px-2 py-0.5 text-xs text-zinc-400">{{ rec.current_tier }}</span>
        </td>
        <td class="whitespace-nowrap px-5 py-3.5">
          <span :class="['rounded-md border px-2 py-0.5 text-xs font-semibold', TIER_COLORS[rec.suggested_tier] ?? 'border-zinc-700 bg-zinc-800 text-zinc-300']">
            {{ rec.suggested_tier }}
          </span>
          <span v-if="rec.current_tier !== rec.suggested_tier" class="ml-1.5 text-xs text-amber-400">← 변경 권장</span>
        </td>
        <td class="px-5 py-3.5 text-sm text-zinc-400">{{ rec.reason }}</td>
      </tr>
    </AdminDataTable>
  </div>
</template>
