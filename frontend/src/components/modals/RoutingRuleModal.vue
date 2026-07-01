<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { XIcon } from 'lucide-vue-next'
import { RoutingRule, RoutingRulePayload } from '../../composables/useApi'
import AppSelect from '../common/AppSelect.vue'

const props = defineProps<{
  rule: RoutingRule | null
}>()

const emit = defineEmits<{
  close: []
  save: [payload: RoutingRulePayload]
  delete: [rule: RoutingRule]
}>()

const isEdit = computed(() => Boolean(props.rule))

const form = reactive<RoutingRulePayload>({
  rule_id: '',
  name: '',
  description: '',
  condition_key: 'general',
  target_tier: 'standard',
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
      condition_key: rule?.condition_key ?? 'general',
      target_tier: rule?.target_tier ?? 'standard',
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
          <p class="mb-1 text-xs font-semibold uppercase tracking-widest text-indigo-400">Routing Rule</p>
          <h3 class="text-lg font-semibold text-zinc-100">{{ isEdit ? 'Rule Detail' : 'New Rule' }}</h3>
        </div>
        <button class="rounded-lg p-1.5 text-zinc-500 transition-colors hover:bg-zinc-800 hover:text-zinc-200" type="button" @click="emit('close')">
          <XIcon class="h-5 w-5" />
        </button>
      </header>

      <form class="p-6" @submit.prevent="emit('save', form)">
        <div class="mb-6 grid grid-cols-1 gap-4 md:grid-cols-2">
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">Rule ID</span>
            <input v-model.trim="form.rule_id" required placeholder="R-07" class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 placeholder-zinc-600 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50" />
          </label>
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">Priority</span>
            <input v-model.number="form.priority" min="1" required type="number" class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50" />
          </label>
          <label class="block md:col-span-2">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">Name</span>
            <input v-model.trim="form.name" required placeholder="Structured output route" class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 placeholder-zinc-600 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50" />
          </label>
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">Condition</span>
            <AppSelect v-model="form.condition_key" :options="[
              { value: 'general', label: 'General/simple query' },
              { value: 'code', label: 'Code or technical request' },
              { value: 'reasoning', label: 'Reasoning request' },
              { value: 'long_context', label: 'Long context request' },
              { value: 'structured_output', label: 'SQL/JSON structured output' },
              { value: 'sensitive', label: 'Sensitive data request' },
              { value: 'always', label: 'Always' }
            ]" />
          </label>
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">Target Tier</span>
            <AppSelect v-model="form.target_tier" :options="[
              { value: 'lightweight', label: 'Lightweight' },
              { value: 'standard', label: 'Standard' },
              { value: 'advanced', label: 'Advanced' },
              { value: 'long_context', label: 'Long Context' },
              { value: 'structured', label: 'Structured' }
            ]" />
          </label>
          <label class="block md:col-span-2">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">Description</span>
            <textarea v-model="form.description" rows="3" placeholder="When this condition matches, prefer models in the selected tier." class="w-full resize-none rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 placeholder-zinc-600 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50"></textarea>
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
            {{ isEdit ? 'Save Changes' : 'Create Rule' }}
          </button>
        </footer>
      </form>
    </div>
  </div>
</template>
