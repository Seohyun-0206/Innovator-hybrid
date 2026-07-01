<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { PlugZapIcon, XIcon } from 'lucide-vue-next'
import { ProviderCredential, ProviderCredentialPayload, ProviderCredentialTestResult, useApi } from '../../composables/useApi'
import AppSelect from '../common/AppSelect.vue'

const props = defineProps<{
  credential: ProviderCredential | null
}>()

const emit = defineEmits<{
  close: []
  save: [payload: ProviderCredentialPayload]
  delete: [credential: ProviderCredential]
}>()

const isEdit = computed(() => Boolean(props.credential))
const api = useApi()
const testing = ref(false)
const testResult = ref<ProviderCredentialTestResult | null>(null)

const form = reactive<ProviderCredentialPayload>({
  provider: 'ollama',
  display_name: '',
  base_url: '',
  access_token: '',
  is_active: true
})

const isOllama = computed(() => form.provider === 'ollama')
const requiresAccessToken = computed(() => !isOllama.value)
const canTestConnection = computed(() => Boolean(form.base_url && (!requiresAccessToken.value || form.access_token)))

watch(
  () => props.credential,
  (credential) => {
    Object.assign(form, {
      provider: credential?.provider ?? 'ollama',
      display_name: credential?.display_name ?? '',
      base_url: credential?.base_url ?? '',
      access_token: '',
      is_active: credential?.is_active ?? true
    })
  },
  { immediate: true }
)

watch(form, () => {
  testResult.value = null
})

async function testConnection() {
  testing.value = true
  testResult.value = null
  try {
    testResult.value = await api.testProviderCredential({
      provider: form.provider,
      base_url: form.base_url,
      access_token: form.access_token
    })
  } catch (err) {
    testResult.value = {
      ok: false,
      status_code: null,
      message: err instanceof Error ? err.message : '연결 테스트에 실패했습니다.'
    }
  } finally {
    testing.value = false
  }
}
</script>

<template>
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm" @click="emit('close')">
    <div class="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-xl border border-zinc-800 bg-zinc-900 shadow-2xl animate-fade-in" @click.stop>
      <header class="flex items-center justify-between border-b border-zinc-800 px-6 py-5">
        <div>
          <p class="mb-1 text-xs font-semibold uppercase tracking-widest text-indigo-400">인증 관리</p>
          <h3 class="text-lg font-semibold text-zinc-100">{{ isEdit ? '인증 정보 상세' : '새 인증 정보' }}</h3>
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
            <AppSelect v-model="form.provider" :options="['ollama', 'openai', 'gemini', 'openrouter']" />
          </label>
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">표시 이름</span>
            <input v-model="form.display_name" required :placeholder="isOllama ? 'RunPod Ollama' : 'OpenAI Production'" class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 placeholder-zinc-600 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50" />
          </label>
          <label class="block md:col-span-2">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">Base URL</span>
            <input v-model="form.base_url" required :placeholder="isOllama ? 'https://your-runpod-host.proxy.runpod.net' : 'https://openrouter.ai/api/v1'" class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 placeholder-zinc-600 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50" />
          </label>
          <label class="block md:col-span-2">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">접근 토큰 {{ isOllama ? '(선택)' : '' }}</span>
            <input
              v-model="form.access_token"
              :required="!isEdit && requiresAccessToken"
              type="password"
              :placeholder="isEdit ? `비워두면 ${credential?.access_token_masked || '현재 토큰'} 유지` : isOllama ? 'RunPod/proxy에서 필요한 경우 Bearer token 입력' : 'API key 또는 access token'"
              class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 placeholder-zinc-600 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50"
            />
            <p v-if="isOllama" class="mt-1 text-xs text-zinc-500">RunPod Ollama는 보통 이 Base URL 아래의 /api/chat, /api/tags 같은 Ollama API 경로를 사용합니다.</p>
            <p v-else-if="isEdit" class="mt-1 text-xs text-zinc-500">새 토큰을 입력하면 저장된 인증 토큰이 교체됩니다.</p>
          </label>
          <label class="flex items-center gap-3 text-sm font-medium text-zinc-400">
            <input v-model="form.is_active" type="checkbox" class="h-4 w-4 rounded border-zinc-600 bg-zinc-800 accent-indigo-500" />
            활성
          </label>
        </div>

        <div
          v-if="testResult"
          :class="[
            'mb-4 rounded-lg border px-3 py-2.5 text-sm',
            testResult.ok
              ? 'border-emerald-500/20 bg-emerald-500/10 text-emerald-400'
              : 'border-red-500/20 bg-red-500/10 text-red-400'
          ]"
        >
          <span class="font-semibold">{{ testResult.ok ? '연결 성공' : '연결 실패' }}</span>
          <span v-if="testResult.status_code"> · HTTP {{ testResult.status_code }}</span>
          <p class="mt-1 text-xs opacity-90">{{ testResult.message }}</p>
        </div>

        <footer class="flex items-center gap-3 border-t border-zinc-800 pt-4">
          <button
            v-if="credential"
            class="rounded-lg border border-red-500/30 px-4 py-2 text-sm font-medium text-red-400 transition-colors hover:bg-red-500/10"
            type="button"
            @click="emit('delete', credential)"
          >
            삭제
          </button>
          <span class="flex-1"></span>
          <button
            class="rounded-lg border border-zinc-700 px-4 py-2 text-sm font-medium text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-zinc-200"
            type="button"
            @click="emit('close')"
          >
            취소
          </button>
          <button
            class="flex items-center gap-2 rounded-lg border border-zinc-700 px-4 py-2 text-sm font-medium text-zinc-300 transition-colors hover:bg-zinc-800 hover:text-zinc-100 disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="testing || !canTestConnection"
            type="button"
            @click="testConnection"
          >
            <div v-if="testing" class="h-4 w-4 animate-spin rounded-full border-2 border-zinc-600 border-t-indigo-500"></div>
            <PlugZapIcon v-else class="h-4 w-4" />
            {{ testing ? '테스트 중...' : '연결 테스트' }}
          </button>
          <button class="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-indigo-500" type="submit">
            {{ isEdit ? '변경사항 저장' : '인증 정보 생성' }}
          </button>
        </footer>
      </form>
    </div>
  </div>
</template>
