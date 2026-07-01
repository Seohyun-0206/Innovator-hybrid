<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { XIcon } from 'lucide-vue-next'
import { RecoveryStrategy, ResponseValidationRule, ResponseValidationRulePayload } from '../../composables/useApi'
import AppSelect from '../common/AppSelect.vue'

const props = defineProps<{
  rule: ResponseValidationRule | null
  strategies: RecoveryStrategy[]
}>()

const emit = defineEmits<{
  close: []
  save: [payload: ResponseValidationRulePayload]
  delete: [rule: ResponseValidationRule]
}>()

const isEdit = computed(() => Boolean(props.rule))
const NONE_STRATEGY = '__none__'

const form = reactive<ResponseValidationRulePayload>({
  rule_id: '',
  name: '',
  description: '',
  recovery_strategy: null,
  condition_key: 'structured_output',
  validation_type: 'json',
  action_on_fail: 'strict_retry',
  retry_prompt: 'Return only valid JSON. Do not include markdown fences, prose, or comments.',
  max_retries: 1,
  target_tier: '',
  priority: 100,
  is_active: true
})

watch(
  () => props.rule,
  (rule) => {
    Object.assign(form, {
      rule_id: rule?.rule_id ?? '',
      name: rule?.name ?? '',
      description: rule?.description ?? '',
      recovery_strategy: rule?.recovery_strategy ?? null,
      condition_key: rule?.condition_key ?? 'structured_output',
      validation_type: rule?.validation_type ?? 'json',
      action_on_fail: rule?.action_on_fail ?? 'strict_retry',
      retry_prompt: rule?.retry_prompt ?? 'Return only valid JSON. Do not include markdown fences, prose, or comments.',
      max_retries: rule?.max_retries ?? 1,
      target_tier: rule?.target_tier ?? '',
      priority: rule?.priority ?? 100,
      is_active: rule?.is_active ?? true
    })
  },
  { immediate: true }
)

const recoveryStrategyOptions = computed(() => [
  { value: NONE_STRATEGY, label: '인라인 조치 사용' },
  ...props.strategies.map((strategy) => ({
    value: String(strategy.id),
    label: `${strategy.name} (${strategy.strategy_id})`
  }))
])

const recoveryStrategyIdStr = computed({
  get: () => (form.recovery_strategy == null ? NONE_STRATEGY : String(form.recovery_strategy)),
  set: (value: string) => {
    form.recovery_strategy = value === NONE_STRATEGY ? null : Number(value)
  }
})
</script>

<template>
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm" @click="emit('close')">
    <div class="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-xl border border-zinc-800 bg-zinc-900 shadow-2xl animate-fade-in" @click.stop>
      <header class="flex items-center justify-between border-b border-zinc-800 px-6 py-5">
        <div>
          <p class="mb-1 text-xs font-semibold uppercase tracking-widest text-indigo-400">응답 규칙</p>
          <h3 class="text-lg font-semibold text-zinc-100">{{ isEdit ? '응답 규칙 상세' : '새 응답 규칙' }}</h3>
        </div>
        <button class="rounded-lg p-1.5 text-zinc-500 transition-colors hover:bg-zinc-800 hover:text-zinc-200" type="button" @click="emit('close')">
          <XIcon class="h-5 w-5" />
        </button>
      </header>

      <form class="p-6" @submit.prevent="emit('save', form)">
        <div class="mb-6 grid grid-cols-1 gap-4 md:grid-cols-2">
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">규칙 ID</span>
            <input v-model.trim="form.rule_id" required placeholder="V-07" class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 placeholder-zinc-600 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50" />
          </label>
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">우선순위</span>
            <input v-model.number="form.priority" min="1" required type="number" class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50" />
          </label>
          <label class="block md:col-span-2">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">이름</span>
            <input v-model.trim="form.name" required placeholder="구조화 JSON 검증" class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 placeholder-zinc-600 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50" />
          </label>
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">조건</span>
            <AppSelect v-model="form.condition_key" :options="[
              { value: 'structured_output', label: 'SQL/JSON 구조화 응답' },
              { value: 'code', label: '코드 또는 기술 요청' },
              { value: 'reasoning', label: '추론 요청' },
              { value: 'long_context', label: '긴 컨텍스트 요청' },
              { value: 'general', label: '일반/단순 질의' },
              { value: 'always', label: '항상 적용' }
            ]" />
          </label>
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">검증 유형</span>
            <AppSelect v-model="form.validation_type" :options="[
              { value: 'json', label: 'JSON 파싱 검증' },
              { value: 'sql', label: 'SQL 형식 검증' },
              { value: 'non_empty', label: '빈 응답 검증' }
            ]" />
          </label>
          <label class="block md:col-span-2">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">복구 전략</span>
            <AppSelect v-model="recoveryStrategyIdStr" :options="recoveryStrategyOptions" />
          </label>
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">실패 시 조치</span>
            <AppSelect v-model="form.action_on_fail" :options="[
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
          <label class="flex items-center gap-3 pt-6 text-sm font-medium text-zinc-400">
            <input v-model="form.is_active" type="checkbox" class="h-4 w-4 rounded border-zinc-600 bg-zinc-800 accent-indigo-500" />
            활성
          </label>
          <label class="block md:col-span-2">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">재시도 프롬프트</span>
            <textarea v-model="form.retry_prompt" rows="3" class="w-full resize-none rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50"></textarea>
          </label>
          <label class="block md:col-span-2">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">설명</span>
            <textarea v-model="form.description" rows="3" class="w-full resize-none rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50"></textarea>
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
            {{ isEdit ? '변경사항 저장' : '응답 규칙 생성' }}
          </button>
        </footer>
      </form>
    </div>
  </div>
</template>
