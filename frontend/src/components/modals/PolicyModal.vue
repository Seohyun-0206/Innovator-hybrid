<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { RoutingPolicy, RoutingPolicyPayload } from '../../composables/useApi'
import { XIcon } from 'lucide-vue-next'

const props = defineProps<{
  policy: RoutingPolicy | null
}>()

const emit = defineEmits<{
  close: []
  save: [payload: RoutingPolicyPayload]
  disable: [policy: RoutingPolicy]
}>()

const isEdit = computed(() => Boolean(props.policy))

const form = reactive<RoutingPolicyPayload>({
  name: '',
  display_name: '',
  description: '',
  priority_config: {
    quality_weight: 1,
    speed_weight: 1,
    cost_weight: 1,
    context_weight: 0,
    local_only: false,
    prefer_coding_models: true,
    prefer_reasoning_models: true,
    min_context_window: 0,
    max_estimated_cost_usd: '',
    fallback_to_local_on_budget: false
  },
  is_active: true
})

watch(
  () => props.policy,
  (policy) => {
    Object.assign(form, {
      name: policy?.name ?? '',
      display_name: policy?.display_name ?? '',
      description: policy?.description ?? '',
      priority_config: {
        quality_weight: policy?.priority_config.quality_weight ?? 1,
        speed_weight: policy?.priority_config.speed_weight ?? 1,
        cost_weight: policy?.priority_config.cost_weight ?? 1,
        context_weight: policy?.priority_config.context_weight ?? 0,
        local_only: policy?.priority_config.local_only ?? false,
        prefer_coding_models: policy?.priority_config.prefer_coding_models ?? true,
        prefer_reasoning_models: policy?.priority_config.prefer_reasoning_models ?? true,
        min_context_window: policy?.priority_config.min_context_window ?? 0,
        max_estimated_cost_usd: policy?.priority_config.max_estimated_cost_usd ?? '',
        fallback_to_local_on_budget: policy?.priority_config.fallback_to_local_on_budget ?? false
      },
      is_active: policy?.is_active ?? true
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
          <p class="mb-1 text-xs font-semibold uppercase tracking-widest text-indigo-400">Routing Policy</p>
          <h3 class="text-lg font-semibold text-zinc-100">{{ isEdit ? 'Policy Detail' : 'New Policy' }}</h3>
        </div>
        <button
          class="rounded-lg p-1.5 text-zinc-500 transition-colors hover:bg-zinc-800 hover:text-zinc-200"
          type="button"
          @click="emit('close')"
        >
          <XIcon class="h-5 w-5" />
        </button>
      </header>

      <form class="p-6" @submit.prevent="emit('save', form)">
        <div class="mb-6 grid grid-cols-1 gap-4 md:grid-cols-2">
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">Name</span>
            <input v-model="form.name" required placeholder="speed-first" class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 placeholder-zinc-600 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50" />
          </label>
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">Display name</span>
            <input v-model="form.display_name" required placeholder="Speed First" class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 placeholder-zinc-600 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50" />
          </label>
          <label class="block md:col-span-2">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">Description</span>
            <textarea v-model="form.description" rows="3" class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 placeholder-zinc-600 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50 resize-vertical" />
          </label>
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">Quality weight</span>
            <input v-model.number="form.priority_config.quality_weight" min="0" type="number" class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50" />
          </label>
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">Speed weight</span>
            <input v-model.number="form.priority_config.speed_weight" min="0" type="number" class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50" />
          </label>
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">Cost weight</span>
            <input v-model.number="form.priority_config.cost_weight" min="0" type="number" class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50" />
          </label>
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">Context weight</span>
            <input v-model.number="form.priority_config.context_weight" min="0" type="number" class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50" />
          </label>
          <label class="flex items-center gap-3 text-sm font-medium text-zinc-400">
            <input v-model="form.priority_config.local_only" type="checkbox" class="h-4 w-4 rounded border-zinc-600 bg-zinc-800 accent-indigo-500" />
            Local only
          </label>
          <label class="flex items-center gap-3 text-sm font-medium text-zinc-400">
            <input v-model="form.priority_config.prefer_coding_models" type="checkbox" class="h-4 w-4 rounded border-zinc-600 bg-zinc-800 accent-indigo-500" />
            Prefer coding models for code prompts
          </label>
          <label class="flex items-center gap-3 text-sm font-medium text-zinc-400">
            <input v-model="form.priority_config.prefer_reasoning_models" type="checkbox" class="h-4 w-4 rounded border-zinc-600 bg-zinc-800 accent-indigo-500" />
            Prefer reasoning models for reasoning prompts
          </label>
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">Minimum context window</span>
            <input v-model.number="form.priority_config.min_context_window" min="0" type="number" class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50" />
          </label>
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">Max estimated cost USD</span>
            <input v-model="form.priority_config.max_estimated_cost_usd" min="0" step="0.000001" type="number" placeholder="0.0005" class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 placeholder-zinc-600 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50" />
          </label>
          <label class="flex items-center gap-3 text-sm font-medium text-zinc-400">
            <input v-model="form.priority_config.fallback_to_local_on_budget" type="checkbox" class="h-4 w-4 rounded border-zinc-600 bg-zinc-800 accent-indigo-500" />
            Fallback to local when budget is exceeded
          </label>
          <label class="flex items-center gap-3 text-sm font-medium text-zinc-400">
            <input v-model="form.is_active" type="checkbox" class="h-4 w-4 rounded border-zinc-600 bg-zinc-800 accent-indigo-500" />
            Active
          </label>
        </div>

        <footer class="flex items-center gap-3 border-t border-zinc-800 pt-4">
          <button
            v-if="policy && policy.is_active"
            class="rounded-lg border border-red-500/30 px-4 py-2 text-sm font-medium text-red-400 transition-colors hover:bg-red-500/10"
            type="button"
            @click="emit('disable', policy)"
          >
            Disable
          </button>
          <span class="flex-1"></span>
          <button
            class="rounded-lg border border-zinc-700 px-4 py-2 text-sm font-medium text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-zinc-200"
            type="button"
            @click="emit('close')"
          >
            Cancel
          </button>
          <button class="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-indigo-500" type="submit">
            {{ isEdit ? 'Save Changes' : 'Create Policy' }}
          </button>
        </footer>
      </form>
    </div>
  </div>
</template>
