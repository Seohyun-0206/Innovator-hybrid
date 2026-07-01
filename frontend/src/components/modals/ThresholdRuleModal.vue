<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { XIcon } from 'lucide-vue-next'
import { ThresholdRule, ThresholdRulePayload } from '../../composables/useApi'
import AppSelect from '../common/AppSelect.vue'

const props = defineProps<{
  rule: ThresholdRule | null
}>()

const emit = defineEmits<{
  close: []
  save: [payload: ThresholdRulePayload]
  delete: [rule: ThresholdRule]
}>()

const isEdit = computed(() => Boolean(props.rule))

const form = reactive<ThresholdRulePayload>({
  rule_id: '',
  name: '',
  description: '',
  metric_key: 'estimated_tokens',
  operator: 'gte',
  threshold_value: '3000.0000',
  action_on_trigger: 'prefer_tier',
  target_tier: 'long_context',
  max_tokens: null,
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
      metric_key: rule?.metric_key ?? 'estimated_tokens',
      operator: rule?.operator ?? 'gte',
      threshold_value: rule?.threshold_value ?? '3000.0000',
      action_on_trigger: rule?.action_on_trigger ?? 'prefer_tier',
      target_tier: rule?.target_tier ?? 'long_context',
      max_tokens: rule?.max_tokens ?? null,
      priority: rule?.priority ?? 100,
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
          <p class="mb-1 text-xs font-semibold uppercase tracking-widest text-indigo-400">Threshold Rule</p>
          <h3 class="text-lg font-semibold text-zinc-100">{{ isEdit ? 'Rule Detail' : 'New Threshold' }}</h3>
        </div>
        <button class="rounded-lg p-1.5 text-zinc-500 transition-colors hover:bg-zinc-800 hover:text-zinc-200" type="button" @click="emit('close')">
          <XIcon class="h-5 w-5" />
        </button>
      </header>

      <form class="p-6" @submit.prevent="emit('save', form)">
        <div class="mb-6 grid grid-cols-1 gap-4 md:grid-cols-2">
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">Rule ID</span>
            <input v-model.trim="form.rule_id" required placeholder="T-08" class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 placeholder-zinc-600 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50" />
          </label>
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">Priority</span>
            <input v-model.number="form.priority" min="1" required type="number" class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50" />
          </label>
          <label class="block md:col-span-2">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">Name</span>
            <input v-model.trim="form.name" required placeholder="Token control path" class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 placeholder-zinc-600 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50" />
          </label>
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">Metric</span>
            <AppSelect v-model="form.metric_key" :options="[
              { value: 'estimated_tokens', label: 'Estimated tokens' },
              { value: 'p95_latency_ms', label: 'p95 latency ms' },
              { value: 'timeout_seconds', label: 'Timeout seconds' },
              { value: 'parse_fail_rate', label: 'Parse fail rate' },
              { value: 'failure_rate', label: 'Failure rate' }
            ]" />
          </label>
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">Operator</span>
            <AppSelect v-model="form.operator" :options="[{ value: 'gte', label: '>=' }, { value: 'lte', label: '<=' }]" />
          </label>
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">Threshold value</span>
            <input v-model="form.threshold_value" min="0" step="0.0001" required type="number" class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50" />
          </label>
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">Action</span>
            <AppSelect v-model="form.action_on_trigger" :options="[{ value: 'prefer_tier', label: 'Prefer model tier' }, { value: 'set_max_tokens', label: 'Set max tokens' }]" />
          </label>
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">Target Tier</span>
            <AppSelect v-model="form.target_tier" :options="[
              { value: '', label: 'No tier target' },
              { value: 'lightweight', label: 'Lightweight' },
              { value: 'standard', label: 'Standard' },
              { value: 'advanced', label: 'Advanced' },
              { value: 'long_context', label: 'Long Context' },
              { value: 'structured', label: 'Structured' }
            ]" />
          </label>
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">Max tokens</span>
            <input v-model.number="form.max_tokens" min="1" type="number" placeholder="optional" class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 placeholder-zinc-600 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50" />
          </label>
          <label class="block md:col-span-2">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">Description</span>
            <textarea v-model="form.description" rows="3" placeholder="Describe when this threshold should trigger." class="w-full resize-none rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 placeholder-zinc-600 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50"></textarea>
          </label>
          <label class="flex items-center gap-3 text-sm font-medium text-zinc-400">
            <input v-model="form.is_active" type="checkbox" class="h-4 w-4 rounded border-zinc-600 bg-zinc-800 accent-indigo-500" />
            Active
          </label>
        </div>

        <footer class="flex items-center gap-3 border-t border-zinc-800 pt-4">
          <button v-if="rule" class="rounded-lg border border-red-500/30 px-4 py-2 text-sm font-medium text-red-400 transition-colors hover:bg-red-500/10" type="button" @click="emit('delete', rule)">
            Delete
          </button>
          <span class="flex-1"></span>
          <button class="rounded-lg border border-zinc-700 px-4 py-2 text-sm font-medium text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-zinc-200" type="button" @click="emit('close')">
            Cancel
          </button>
          <button class="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-indigo-500" type="submit">
            {{ isEdit ? 'Save Changes' : 'Create Threshold' }}
          </button>
        </footer>
      </form>
    </div>
  </div>
</template>
