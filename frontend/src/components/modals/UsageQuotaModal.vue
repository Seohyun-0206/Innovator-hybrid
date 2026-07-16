<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { XIcon } from 'lucide-vue-next'
import { AppUser, UsageQuota, UsageQuotaPayload } from '../../composables/useApi'
import AppSelect from '../common/AppSelect.vue'

const props = defineProps<{
  quota: UsageQuota | null
  users: AppUser[]
}>()

const emit = defineEmits<{
  close: []
  save: [payload: UsageQuotaPayload]
  delete: [quota: UsageQuota]
}>()

const isEdit = computed(() => Boolean(props.quota))
const ALL_USERS = '__all__'

const form = reactive<UsageQuotaPayload>({
  name: '',
  user: null,
  provider: '',
  monthly_request_limit: null,
  monthly_cost_limit_usd: null,
  action_on_exceed: 'local_fallback',
  is_active: true
})

const userIdStr = computed({
  get: () => (form.user == null ? ALL_USERS : String(form.user)),
  set: (value: string) => {
    form.user = value === ALL_USERS ? null : Number(value)
  }
})

const userOptions = computed(() => [
  { value: ALL_USERS, label: '전체 사용자' },
  ...props.users.map((user) => ({ value: String(user.id), label: user.username }))
])

watch(
  () => props.quota,
  (quota) => {
    Object.assign(form, {
      name: quota?.name ?? '',
      user: quota?.user ?? null,
      provider: quota?.provider ?? '',
      monthly_request_limit: quota?.monthly_request_limit ?? null,
      monthly_cost_limit_usd: quota?.monthly_cost_limit_usd ?? null,
      action_on_exceed: quota?.action_on_exceed ?? 'local_fallback',
      is_active: quota?.is_active ?? true
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
          <p class="mb-1 text-xs font-semibold uppercase tracking-widest text-indigo-400">사용량 한도</p>
          <h3 class="text-lg font-semibold text-zinc-100">{{ isEdit ? '한도 상세' : '새 한도' }}</h3>
        </div>
        <button class="rounded-lg p-1.5 text-zinc-500 transition-colors hover:bg-zinc-800 hover:text-zinc-200" type="button" @click="emit('close')">
          <XIcon class="h-5 w-5" />
        </button>
      </header>

      <form class="p-6" @submit.prevent="emit('save', form)">
        <div class="mb-6 grid grid-cols-1 gap-4 md:grid-cols-2">
          <label class="block md:col-span-2">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">이름</span>
            <input v-model="form.name" required placeholder="OpenRouter 월간 한도" class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 placeholder-zinc-600 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50" />
          </label>
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">사용자</span>
            <AppSelect v-model="userIdStr" :options="userOptions" />
          </label>
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">Provider</span>
            <AppSelect v-model="form.provider" :options="[{ value: '', label: '전체 Provider' }, 'ollama', 'openai', 'gemini', 'openrouter', 'anthropic']" />
          </label>
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">월간 요청 수</span>
            <input v-model.number="form.monthly_request_limit" min="0" type="number" placeholder="1000" class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 placeholder-zinc-600 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50" />
          </label>
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">월간 비용(USD)</span>
            <input v-model="form.monthly_cost_limit_usd" min="0" step="0.000001" type="number" placeholder="10.000000" class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 placeholder-zinc-600 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50" />
          </label>
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">초과 시 조치</span>
            <AppSelect v-model="form.action_on_exceed" :options="[{ value: 'local_fallback', label: '로컬 fallback' }, { value: 'block', label: '요청 차단' }]" />
          </label>
          <label class="flex items-center gap-3 pt-6 text-sm font-medium text-zinc-400">
            <input v-model="form.is_active" type="checkbox" class="h-4 w-4 rounded border-zinc-600 bg-zinc-800 accent-indigo-500" />
            활성
          </label>
        </div>

        <footer class="flex items-center gap-3 border-t border-zinc-800 pt-4">
          <button v-if="quota" class="rounded-lg border border-red-500/30 px-4 py-2 text-sm font-medium text-red-400 transition-colors hover:bg-red-500/10" type="button" @click="emit('delete', quota)">
            삭제
          </button>
          <span class="flex-1"></span>
          <button class="rounded-lg border border-zinc-700 px-4 py-2 text-sm font-medium text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-zinc-200" type="button" @click="emit('close')">
            취소
          </button>
          <button class="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-indigo-500" type="submit">
            {{ isEdit ? '변경사항 저장' : '한도 생성' }}
          </button>
        </footer>
      </form>
    </div>
  </div>
</template>
