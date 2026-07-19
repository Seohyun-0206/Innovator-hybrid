<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { XIcon } from 'lucide-vue-next'
import { ModelHealthRule, ModelHealthRulePayload } from '../../composables/useApi'
import AppSelect from '../common/AppSelect.vue'

const props = defineProps<{
  rule: ModelHealthRule | null
}>()

const emit = defineEmits<{
  close: []
  save: [payload: ModelHealthRulePayload]
  delete: [rule: ModelHealthRule]
}>()

const isEdit = computed(() => Boolean(props.rule))

const form = reactive<ModelHealthRulePayload>({
  name: '',
  provider: '',
  model_name: '',
  window_minutes: 60,
  min_requests: 5,
  max_failure_rate_percent: '50.00',
  max_average_latency_ms: null,
  action_on_trigger: 'exclude',
  is_active: true
})

watch(
  () => props.rule,
  (rule) => {
    Object.assign(form, {
      name: rule?.name ?? '',
      provider: rule?.provider ?? '',
      model_name: rule?.model_name ?? '',
      window_minutes: rule?.window_minutes ?? 60,
      min_requests: rule?.min_requests ?? 5,
      max_failure_rate_percent: rule?.max_failure_rate_percent ?? '50.00',
      max_average_latency_ms: rule?.max_average_latency_ms ?? null,
      action_on_trigger: rule?.action_on_trigger ?? 'exclude',
      is_active: rule?.is_active ?? true
    })
  },
  { immediate: true }
)
</script>

<template>
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm" @click="emit('close')">
    <div class="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-xl border border-zinc-800 bg-zinc-900 shadow-2xl animate-fade-in" @click.stop>
      <header class="flex items-center justify-between border-b border-zinc-800 px-6 py-5">
        <div>
          <p class="mb-1 text-xs font-semibold uppercase tracking-widest text-indigo-400">모델 상태 규칙</p>
          <h3 class="text-lg font-semibold text-zinc-100">{{ isEdit ? '규칙 상세' : '새 규칙' }}</h3>
        </div>
        <button class="rounded-lg p-1.5 text-zinc-500 transition-colors hover:bg-zinc-800 hover:text-zinc-200" type="button" @click="emit('close')">
          <XIcon class="h-5 w-5" />
        </button>
      </header>

      <form class="p-6" @submit.prevent="emit('save', form)">
        <div class="mb-6 grid grid-cols-1 gap-4 md:grid-cols-2">
          <label class="block md:col-span-2">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">이름</span>
            <input v-model="form.name" required placeholder="OpenRouter 실패율 가드" class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 placeholder-zinc-600 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50" />
          </label>
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">Provider</span>
            <AppSelect v-model="form.provider" :options="[{ value: '', label: 'All providers' }, 'ollama', 'openai', 'gemini', 'openrouter', 'anthropic', 'vllm']" />
          </label>
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">모델명</span>
            <input v-model.trim="form.model_name" placeholder="비워두면 전체 모델" class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 placeholder-zinc-600 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50" />
          </label>
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">집계 기간(분)</span>
            <input v-model.number="form.window_minutes" min="1" required type="number" class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50" />
          </label>
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">최소 요청 수</span>
            <input v-model.number="form.min_requests" min="1" required type="number" class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50" />
          </label>
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">최대 실패율 %</span>
            <input v-model="form.max_failure_rate_percent" min="0" max="100" step="0.01" type="number" placeholder="50.00" class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 placeholder-zinc-600 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50" />
          </label>
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">최대 평균 지연(ms)</span>
            <input v-model.number="form.max_average_latency_ms" min="0" type="number" placeholder="10000" class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 placeholder-zinc-600 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50" />
          </label>
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">조치</span>
            <AppSelect v-model="form.action_on_trigger" :options="[{ value: 'exclude', label: '라우팅에서 제외' }]" />
          </label>
          <label class="flex items-center gap-3 pt-6 text-sm font-medium text-zinc-400">
            <input v-model="form.is_active" type="checkbox" class="h-4 w-4 rounded border-zinc-600 bg-zinc-800 accent-indigo-500" />
            활성
          </label>
        </div>

        <footer class="flex items-center gap-3 border-t border-zinc-800 pt-4">
          <button v-if="rule" class="rounded-lg border border-red-500/30 px-4 py-2 text-sm font-medium text-red-400 transition-colors hover:bg-red-500/10" type="button" @click="emit('delete', rule)">
            삭제
          </button>
          <span class="flex-1"></span>
          <button class="rounded-lg border border-zinc-700 px-4 py-2 text-sm font-medium text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-zinc-200" type="button" @click="emit('close')">
            취소
          </button>
          <button class="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-indigo-500" type="submit">
            {{ isEdit ? '변경사항 저장' : '규칙 생성' }}
          </button>
        </footer>
      </form>
    </div>
  </div>
</template>
