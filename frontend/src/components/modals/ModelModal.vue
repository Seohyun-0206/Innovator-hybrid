<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { XIcon } from 'lucide-vue-next'
import { LLMModel, LLMModelPayload, ProviderCredential } from '../../composables/useApi'
import AppSelect from '../common/AppSelect.vue'

const props = defineProps<{
  model: LLMModel | null
  credentials: ProviderCredential[]
}>()

const emit = defineEmits<{
  close: []
  save: [payload: LLMModelPayload]
  disable: [model: LLMModel]
}>()

const isEdit = computed(() => Boolean(props.model))
const credentialProviders = ['ollama', 'openai', 'gemini', 'openrouter', 'anthropic']
const remoteCapableProviders = ['ollama']
const usesCredential = computed(() => credentialProviders.includes(form.provider))
const matchingCredentials = computed(() =>
  props.credentials.filter((credential) => credential.provider === form.provider)
)

const form = reactive<LLMModelPayload>({
  provider: 'ollama',
  name: '',
  display_name: '',
  model_tier: 'standard',
  provider_credential: null,
  role: 'general',
  quality_level: 3,
  speed_level: 3,
  cost_level: 1,
  privacy_level: 'local',
  context_window: 8192,
  input_token_price_per_1m: '0.0000',
  output_token_price_per_1m: '0.0000',
  average_latency_ms: 0,
  timeout_seconds: 120,
  is_active: true
})

watch(
  () => props.model,
  (model) => {
    Object.assign(form, {
      provider: model?.provider ?? 'ollama',
      name: model?.name ?? '',
      display_name: model?.display_name ?? '',
      model_tier: model?.model_tier ?? 'standard',
      provider_credential: model?.provider_credential ?? null,
      role: model?.role ?? 'general',
      quality_level: model?.quality_level ?? 3,
      speed_level: model?.speed_level ?? 3,
      cost_level: model?.cost_level ?? 1,
      privacy_level: model?.privacy_level ?? 'local',
      context_window: model?.context_window ?? 8192,
      input_token_price_per_1m: model?.input_token_price_per_1m ?? '0.0000',
      output_token_price_per_1m: model?.output_token_price_per_1m ?? '0.0000',
      average_latency_ms: model?.average_latency_ms ?? 0,
      timeout_seconds: model?.timeout_seconds ?? 120,
      is_active: model?.is_active ?? true
    })
  },
  { immediate: true }
)

watch(
  () => form.provider,
  () => {
    if (!usesCredential.value) {
      form.provider_credential = null
      form.privacy_level = 'local'
      return
    }
    form.privacy_level = remoteCapableProviders.includes(form.provider) ? form.privacy_level : 'external'
    if (
      form.provider_credential &&
      !matchingCredentials.value.some((credential) => credential.id === form.provider_credential)
    ) {
      form.provider_credential = null
    }
  }
)

watch(
  () => form.provider_credential,
  () => {
    if (form.provider === 'ollama' && form.provider_credential) {
      form.privacy_level = 'external'
    }
  }
)

const NONE_CREDENTIAL = '__none__'

const credentialOptions = computed(() => [
  { value: NONE_CREDENTIAL, label: 'Provider default credential' },
  ...matchingCredentials.value.map((c) => ({
    value: String(c.id),
    label: c.display_name + (c.is_active ? '' : ' (inactive)')
  }))
])

const credentialIdStr = computed({
  get: () => (form.provider_credential == null ? NONE_CREDENTIAL : String(form.provider_credential)),
  set: (val: string) => {
    form.provider_credential = val === NONE_CREDENTIAL ? null : Number(val)
  }
})
</script>

<template>
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm" @click="emit('close')">
    <div class="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-xl border border-zinc-800 bg-zinc-900 shadow-2xl animate-fade-in" @click.stop>
      <header class="flex items-center justify-between border-b border-zinc-800 px-6 py-5">
        <div>
          <p class="mb-1 text-xs font-semibold uppercase tracking-widest text-indigo-400">모델</p>
          <h3 class="text-lg font-semibold text-zinc-100">{{ isEdit ? '모델 상세' : '새 모델' }}</h3>
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
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">Provider</span>
            <AppSelect v-model="form.provider" :options="['ollama', 'openai', 'gemini', 'openrouter', 'anthropic']" />
          </label>
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">Role</span>
            <AppSelect v-model="form.role" :options="['general', 'coding', 'reasoning', 'summary']" />
          </label>
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">Model Tier</span>
            <AppSelect v-model="form.model_tier" :options="[
              { value: 'lightweight', label: 'Lightweight' },
              { value: 'standard', label: 'Standard' },
              { value: 'advanced', label: 'Advanced' },
              { value: 'long_context', label: 'Long Context' },
              { value: 'structured', label: 'Structured' }
            ]" />
          </label>
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">Model name</span>
            <input v-model="form.name" required placeholder="openai/gpt-4.1-mini" class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 placeholder-zinc-600 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50" />
          </label>
          <label v-if="usesCredential" class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">Credential</span>
            <AppSelect v-model="credentialIdStr" :options="credentialOptions" />
          </label>
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">Display name</span>
            <input v-model="form.display_name" required placeholder="Llama 3.1 8B" class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 placeholder-zinc-600 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50" />
          </label>
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">Quality level</span>
            <input v-model.number="form.quality_level" min="1" max="5" type="number" class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50" />
          </label>
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">Speed level</span>
            <input v-model.number="form.speed_level" min="1" max="5" type="number" class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50" />
          </label>
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">Cost level</span>
            <input v-model.number="form.cost_level" min="1" max="5" type="number" class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50" />
          </label>
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">Context window</span>
            <input v-model.number="form.context_window" min="1" type="number" class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50" />
          </label>
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">Input $ / 1M tokens</span>
            <input v-model="form.input_token_price_per_1m" min="0" step="0.0001" type="number" class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50" />
          </label>
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">Output $ / 1M tokens</span>
            <input v-model="form.output_token_price_per_1m" min="0" step="0.0001" type="number" class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50" />
          </label>
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">Avg latency ms</span>
            <input v-model.number="form.average_latency_ms" min="0" type="number" class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50" />
          </label>
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">Timeout seconds</span>
            <input v-model.number="form.timeout_seconds" min="1" type="number" class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50" />
          </label>
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">Privacy</span>
            <AppSelect v-model="form.privacy_level" :options="['local', 'external']" />
          </label>
          <label class="flex items-center gap-3 pt-6 text-sm font-medium text-zinc-400">
            <input v-model="form.is_active" type="checkbox" class="h-4 w-4 rounded border-zinc-600 bg-zinc-800 accent-indigo-500" />
            Active
          </label>
        </div>

        <footer class="flex items-center gap-3 border-t border-zinc-800 pt-4">
          <button
            v-if="model && model.is_active"
            class="rounded-lg border border-red-500/30 px-4 py-2 text-sm font-medium text-red-400 transition-colors hover:bg-red-500/10"
            type="button"
            @click="emit('disable', model)"
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
            {{ isEdit ? 'Save Changes' : 'Create Model' }}
          </button>
        </footer>
      </form>
    </div>
  </div>
</template>
