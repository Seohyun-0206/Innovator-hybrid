<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { SendIcon, ZapIcon } from 'lucide-vue-next'
import { ChatResponse, RoutingPolicy, useApi } from '../composables/useApi'
import AppSelect, { SelectOption } from '../components/common/AppSelect.vue'

const api = useApi()
const prompt = ref('Django API에서 발생한 stacktrace를 분석하고 해결 방향을 알려줘.')
const policy = ref('cost-first')
const policies = ref<RoutingPolicy[]>([])
const result = ref<ChatResponse | null>(null)
const error = ref('')
const loading = ref(false)

async function submit() {
  loading.value = true
  error.value = ''
  result.value = null
  try {
    result.value = await api.chat(prompt.value, policy.value)
  } catch (err) {
    error.value = err instanceof Error ? err.message : '요청에 실패했습니다.'
  } finally {
    loading.value = false
  }
}

const policyOptions = computed<SelectOption[]>(() =>
  policies.value.map((p) => ({ value: p.name, label: `${p.display_name} (${p.name})` }))
)

onMounted(async () => {
  policies.value = (await api.getPolicies()).filter((item) => item.is_active)
  if (!policies.value.some((item) => item.name === policy.value) && policies.value[0]) {
    policy.value = policies.value[0].name
  }
})
</script>

<template>
  <div class="p-6 lg:p-8">
    <!-- Page header -->
    <div class="mb-8">
      <p class="mb-1 text-xs font-semibold uppercase tracking-widest text-indigo-400">라우팅</p>
      <h2 class="text-2xl font-bold text-zinc-100">테스트</h2>
    </div>

    <div class="grid gap-6 lg:grid-cols-2">
      <!-- Input panel -->
      <div class="flex flex-col gap-4 rounded-xl border border-zinc-800 bg-zinc-900 p-5">
        <h3 class="text-sm font-semibold text-zinc-200">요청</h3>

        <label class="block">
          <span class="mb-1.5 block text-xs font-medium text-zinc-400">정책</span>
          <AppSelect v-model="policy" :options="policyOptions" />
        </label>

        <label class="block flex-1">
          <span class="mb-1.5 block text-xs font-medium text-zinc-400">프롬프트</span>
          <textarea
            v-model="prompt"
            rows="10"
            class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 placeholder-zinc-600 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50 resize-vertical"
          />
        </label>

        <button
          class="flex items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-indigo-500/20 transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-50"
          :disabled="loading || !prompt.trim()"
          @click="submit"
        >
          <div v-if="loading" class="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white"></div>
          <SendIcon v-else class="h-4 w-4" />
          {{ loading ? '라우팅 중...' : 'Gateway로 전송' }}
        </button>
      </div>

      <!-- Result panel -->
      <div class="rounded-xl border border-zinc-800 bg-zinc-900 p-5">
        <h3 class="mb-4 text-sm font-semibold text-zinc-200">라우팅 결과</h3>

        <div v-if="error" class="rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2.5 text-sm text-red-400">
          {{ error }}
        </div>

        <div v-else-if="result" class="space-y-4">
          <!-- Routing meta -->
          <div class="grid grid-cols-3 gap-3">
            <div class="rounded-lg bg-zinc-800/60 p-3">
              <p class="mb-1 text-[10px] font-medium uppercase tracking-wide text-zinc-500">모델</p>
              <p class="text-sm font-semibold text-zinc-200 truncate">{{ result.selected_provider }}/{{ result.selected_model }}</p>
            </div>
            <div class="rounded-lg bg-zinc-800/60 p-3">
              <p class="mb-1 text-[10px] font-medium uppercase tracking-wide text-zinc-500">지연</p>
              <p class="text-sm font-semibold text-zinc-200">{{ result.latency_ms }}ms</p>
            </div>
            <div class="rounded-lg bg-zinc-800/60 p-3">
              <p class="mb-1 text-[10px] font-medium uppercase tracking-wide text-zinc-500">토큰</p>
              <p class="text-sm font-semibold text-zinc-200">{{ result.estimated_tokens }}</p>
            </div>
          </div>

          <!-- Routing reason -->
          <div>
            <div class="mb-1.5 flex items-center gap-1.5">
              <ZapIcon class="h-3.5 w-3.5 text-amber-400" />
              <p class="text-xs font-semibold uppercase tracking-wide text-zinc-400">라우팅 사유</p>
            </div>
            <p class="text-sm text-zinc-300 leading-relaxed">{{ result.routing_reason }}</p>
          </div>

          <!-- Response -->
          <div>
            <p class="mb-1.5 text-xs font-semibold uppercase tracking-wide text-zinc-400">응답</p>
            <pre class="overflow-auto rounded-lg bg-zinc-950 p-4 text-xs text-zinc-300 leading-relaxed max-h-64 whitespace-pre-wrap border border-zinc-800">{{ result.response_text || result.error_message }}</pre>
          </div>
        </div>

        <div v-else class="flex flex-col items-center justify-center py-16 text-center">
          <SendIcon class="mb-3 h-8 w-8 text-zinc-700" />
          <p class="text-sm text-zinc-500">프롬프트를 전송하면 선택 모델,<br />라우팅 사유, 지연 시간을 확인할 수 있습니다.</p>
        </div>
      </div>
    </div>
  </div>
</template>
