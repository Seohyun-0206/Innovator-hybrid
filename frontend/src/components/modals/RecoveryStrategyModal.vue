<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { XIcon } from 'lucide-vue-next'
import { RecoveryStrategy, RecoveryStrategyPayload } from '../../composables/useApi'
import AppSelect from '../common/AppSelect.vue'

const props = defineProps<{ strategy: RecoveryStrategy | null }>()

const emit = defineEmits<{
  close: []
  save: [payload: RecoveryStrategyPayload]
  delete: [strategy: RecoveryStrategy]
}>()

const isEdit = computed(() => Boolean(props.strategy))

const form = reactive<RecoveryStrategyPayload>({
  strategy_id: '',
  name: '',
  description: '',
  trigger_event: 'validation_fail',
  action: 'strict_retry',
  retry_prompt: 'Return only valid JSON. Do not include markdown fences, prose, or comments.',
  max_retries: 1,
  target_tier: '',
  priority: 100,
  is_active: true
})

watch(
  () => props.strategy,
  (strategy) => {
    Object.assign(form, {
      strategy_id: strategy?.strategy_id ?? '',
      name: strategy?.name ?? '',
      description: strategy?.description ?? '',
      trigger_event: strategy?.trigger_event ?? 'validation_fail',
      action: strategy?.action ?? 'strict_retry',
      retry_prompt: strategy?.retry_prompt ?? 'Return only valid JSON. Do not include markdown fences, prose, or comments.',
      max_retries: strategy?.max_retries ?? 1,
      target_tier: strategy?.target_tier ?? '',
      priority: strategy?.priority ?? 100,
      is_active: strategy?.is_active ?? true
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
          <p class="mb-1 text-xs font-semibold uppercase tracking-widest text-indigo-400">복구 전략</p>
          <h3 class="text-lg font-semibold text-zinc-100">{{ isEdit ? '복구 전략 상세' : '새 복구 전략' }}</h3>
        </div>
        <button class="rounded-lg p-1.5 text-zinc-500 transition-colors hover:bg-zinc-800 hover:text-zinc-200" type="button" @click="emit('close')">
          <XIcon class="h-5 w-5" />
        </button>
      </header>

      <form class="p-6" @submit.prevent="emit('save', form)">
        <div class="mb-6 grid grid-cols-1 gap-4 md:grid-cols-2">
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">전략 ID</span>
            <input v-model.trim="form.strategy_id" required placeholder="S-01" class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50" />
          </label>
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">우선순위</span>
            <input v-model.number="form.priority" min="1" required type="number" class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50" />
          </label>
          <label class="block md:col-span-2">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">이름</span>
            <input v-model.trim="form.name" required placeholder="엄격 재시도 후 fallback" class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50" />
          </label>
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">트리거</span>
            <AppSelect v-model="form.trigger_event" :options="[
              { value: 'validation_fail', label: '검증 실패' },
              { value: 'timeout', label: '타임아웃' },
              { value: 'api_fail', label: 'API 실패' },
              { value: 'parse_fail', label: '파싱 실패' },
              { value: 'low_confidence', label: '낮은 신뢰도' }
            ]" />
          </label>
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">조치</span>
            <AppSelect v-model="form.action" :options="[
              { value: 'strict_retry', label: '엄격 재시도' },
              { value: 'fallback', label: 'Fallback' },
              { value: 'escalate', label: 'Tier로 escalation' },
              { value: 'block', label: '응답 차단' }
            ]" />
          </label>
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">최대 재시도</span>
            <input v-model.number="form.max_retries" min="0" required type="number" class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50" />
          </label>
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">Escalation Tier</span>
            <AppSelect v-model="form.target_tier" :options="[
              { value: '', label: '대상 Tier 없음' },
              { value: 'advanced', label: 'Advanced' },
              { value: 'structured', label: 'Structured' },
              { value: 'long_context', label: 'Long Context' },
              { value: 'standard', label: 'Standard' },
              { value: 'lightweight', label: 'Lightweight' }
            ]" />
          </label>
          <label class="block md:col-span-2">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">재시도 프롬프트</span>
            <textarea v-model="form.retry_prompt" rows="3" class="w-full resize-none rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50"></textarea>
          </label>
          <label class="block md:col-span-2">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">설명</span>
            <textarea v-model="form.description" rows="3" class="w-full resize-none rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50"></textarea>
          </label>
          <label class="flex items-center gap-3 text-sm font-medium text-zinc-400">
            <input v-model="form.is_active" type="checkbox" class="h-4 w-4 rounded border-zinc-600 bg-zinc-800 accent-indigo-500" />
            활성
          </label>
        </div>

        <footer class="flex items-center gap-3 border-t border-zinc-800 pt-4">
          <button v-if="strategy" class="rounded-lg border border-red-500/30 px-4 py-2 text-sm font-medium text-red-400 transition-colors hover:bg-red-500/10" type="button" @click="emit('delete', strategy)">
            삭제
          </button>
          <span class="flex-1"></span>
          <button class="rounded-lg border border-zinc-700 px-4 py-2 text-sm font-medium text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-zinc-200" type="button" @click="emit('close')">
            취소
          </button>
          <button class="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-indigo-500" type="submit">
            {{ isEdit ? '변경사항 저장' : '복구 전략 생성' }}
          </button>
        </footer>
      </form>
    </div>
  </div>
</template>
