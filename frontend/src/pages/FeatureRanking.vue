<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { BarChart3Icon } from 'lucide-vue-next'
import AppSelect, { SelectOption } from '../components/common/AppSelect.vue'
import { LLMModel, ServiceFeature, TierRecommendation, useApi } from '../composables/useApi'

const api = useApi()
const models = ref<LLMModel[]>([])
const features = ref<ServiceFeature[]>([])
const recommendations = ref<TierRecommendation[]>([])
const loading = ref(false)
const preset = ref('balanced')

const PRESET_OPTIONS: SelectOption[] = [
  { value: 'balanced', label: '균형 우선' },
  { value: 'cost-first', label: '비용 우선' },
  { value: 'quality-first', label: '품질 우선' },
  { value: 'privacy-first', label: '보안 우선' },
]

const TIER_COLORS: Record<string, string> = {
  lightweight: 'border-emerald-500/20 bg-emerald-500/10 text-emerald-400',
  standard: 'border-sky-500/20 bg-sky-500/10 text-sky-300',
  advanced: 'border-violet-500/20 bg-violet-500/10 text-violet-400',
  long_context: 'border-amber-500/20 bg-amber-500/10 text-amber-400',
  structured: 'border-rose-500/20 bg-rose-500/10 text-rose-400',
}

function sortScore(m: LLMModel, p: string): number {
  if (p === 'cost-first') return m.cost_level * 10 - m.quality_level
  if (p === 'quality-first') return -m.quality_level * 10 + m.cost_level
  if (p === 'privacy-first') return (m.privacy_level === 'local' ? 0 : 100) - m.quality_level
  return -(m.quality_level + m.speed_level - m.cost_level)
}

const featureRankings = computed(() =>
  features.value
    .filter((f) => f.is_active)
    .map((feature) => {
      const suggestedTierMap = Object.fromEntries(recommendations.value.map((r) => [r.model_id, r.suggested_tier]))
      const candidates = models.value
        .filter((m) => m.is_active && suggestedTierMap[m.id] === feature.required_tier)
        .sort((a, b) => sortScore(a, preset.value) - sortScore(b, preset.value))
      const missing = candidates.length === 0
      return { feature, candidates, missing }
    })
)

async function load() {
  loading.value = true
  try {
    const [m, f, r] = await Promise.all([api.getModels(), api.getServiceFeatures(), api.getTierRecommendations()])
    models.value = m
    features.value = f
    recommendations.value = r
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
        <h2 class="text-2xl font-bold text-zinc-100">기능별 모델 순위</h2>
        <p class="mt-1 text-sm text-zinc-500">대상 서비스별 후보 모델과 우선순위를 확인합니다. 실제 우선순위는 초안 생성 화면에서 조정할 수 있습니다.</p>
      </div>
    </div>

    <div class="mb-6 flex items-center gap-3">
      <span class="text-sm text-zinc-400">순위 기준:</span>
      <div class="w-44">
        <AppSelect v-model="preset" :options="PRESET_OPTIONS" />
      </div>
    </div>

    <div v-if="loading" class="flex items-center justify-center py-20 text-zinc-500">
      <div class="h-5 w-5 animate-spin rounded-full border-2 border-zinc-700 border-t-indigo-500 mr-3"></div>
      불러오는 중...
    </div>

    <div v-else-if="featureRankings.length === 0" class="flex flex-col items-center justify-center py-20 text-center">
      <BarChart3Icon class="mb-4 h-12 w-12 text-zinc-700" />
      <p class="text-sm font-semibold text-zinc-300">정의된 대상 서비스가 없습니다</p>
      <p class="text-sm text-zinc-600">대상 서비스 화면에서 항목을 추가하세요.</p>
    </div>

    <div v-else class="space-y-5">
      <div v-for="{ feature, candidates, missing } in featureRankings" :key="feature.id" class="rounded-xl border border-zinc-800 bg-zinc-900 p-5">
        <div class="mb-4 flex flex-wrap items-center gap-3">
          <div class="flex-1">
            <h3 class="font-semibold text-zinc-100">{{ feature.name }}</h3>
            <p class="text-xs text-zinc-500 mt-0.5">{{ feature.description }}</p>
          </div>
          <div class="flex items-center gap-2">
            <span :class="['rounded-md border px-2 py-0.5 text-xs font-medium', TIER_COLORS[feature.required_tier] ?? 'border-zinc-700 text-zinc-300']">{{ feature.required_tier }}</span>
            <span class="rounded-md border border-zinc-700 bg-zinc-800 px-2 py-0.5 text-xs text-zinc-400">{{ feature.condition_key }}</span>
            <span class="rounded-md border border-zinc-700 bg-zinc-800 px-2 py-0.5 text-xs text-zinc-400">{{ feature.routing_path }}</span>
          </div>
        </div>

        <div v-if="missing" class="rounded-lg border border-amber-500/20 bg-amber-500/5 px-3 py-2.5 text-sm text-amber-400">
          <strong>{{ feature.required_tier }}</strong> Tier에 사용할 수 있는 모델이 없습니다. 초안 생성 화면에서 모델을 선택하면 fallback 후보가 할당됩니다.
        </div>

        <div v-else class="space-y-2">
          <div v-for="(model, idx) in candidates" :key="model.id" class="flex items-center gap-3 rounded-lg border border-zinc-800 bg-zinc-800/40 px-3 py-2.5">
            <span class="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold" :class="idx === 0 ? 'bg-indigo-600 text-white' : 'bg-zinc-700 text-zinc-400'">#{{ idx + 1 }}</span>
            <div class="flex-1 min-w-0">
              <p class="truncate text-sm font-medium text-zinc-200">{{ model.display_name }}</p>
              <p class="text-xs text-zinc-500">{{ model.provider }}/{{ model.name }}</p>
            </div>
            <div class="flex items-center gap-1.5 text-xs text-zinc-500">
              <span>Q{{ model.quality_level }}</span>
              <span>S{{ model.speed_level }}</span>
              <span>C{{ model.cost_level }}</span>
              <span :class="model.privacy_level === 'local' ? 'text-emerald-400' : 'text-amber-400'">{{ model.privacy_level }}</span>
            </div>
          </div>
        </div>

        <div v-if="feature.main_metrics.length" class="mt-3 flex flex-wrap gap-1.5">
          <span class="text-xs text-zinc-600">주요 지표:</span>
          <span v-for="m in feature.main_metrics" :key="m" class="rounded border border-zinc-700 bg-zinc-800 px-1.5 py-0.5 text-xs text-zinc-400">{{ m }}</span>
        </div>
      </div>
    </div>
  </div>
</template>
