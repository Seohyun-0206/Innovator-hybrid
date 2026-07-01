<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ShieldIcon } from 'lucide-vue-next'
import AppSelect from '../components/common/AppSelect.vue'
import { SecurityPolicyPayload, useApi } from '../composables/useApi'

const api = useApi()
const loading = ref(false)
const saving = ref(false)
const message = ref('')
const error = ref('')

const form = reactive<SecurityPolicyPayload>({
  max_sessions_user: 1,
  max_sessions_staff: 3,
  idle_timeout_minutes: 30,
  absolute_timeout_hours: 12,
  on_session_limit: 'revoke_oldest',
  revoke_sessions_on_permission_change: true,
  block_inactive_user_login: true
})

async function loadPolicy() {
  loading.value = true
  try {
    Object.assign(form, await api.getSecurityPolicy())
  } finally {
    loading.value = false
  }
}

async function savePolicy() {
  saving.value = true
  error.value = ''
  message.value = ''
  try {
    Object.assign(form, await api.updateSecurityPolicy(form))
    message.value = 'Security policy saved.'
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to save security policy'
  } finally {
    saving.value = false
  }
}

onMounted(loadPolicy)
</script>

<template>
  <div class="p-6 lg:p-8">
    <div class="mb-6">
      <p class="mb-1 text-xs font-semibold uppercase tracking-widest text-indigo-400">시스템 관리</p>
      <h2 class="text-2xl font-bold text-zinc-100">보안 설정</h2>
    </div>

    <div v-if="loading" class="flex items-center gap-3 text-zinc-500">
      <div class="h-4 w-4 animate-spin rounded-full border-2 border-zinc-700 border-t-indigo-500"></div>
      <span class="text-sm">보안 정책을 불러오는 중...</span>
    </div>

    <form v-else class="max-w-4xl rounded-xl border border-zinc-800 bg-zinc-900 p-6" @submit.prevent="savePolicy">
      <div class="mb-6 flex items-start gap-3 rounded-lg border border-indigo-500/20 bg-indigo-500/10 p-4">
        <ShieldIcon class="mt-0.5 h-5 w-5 text-indigo-300" />
        <div>
          <p class="text-sm font-semibold text-zinc-100">세션 제어 정책</p>
          <p class="mt-1 text-sm text-zinc-500">관리형 로그인 세션에 대해 백엔드에서 강제 적용되는 설정입니다.</p>
        </div>
      </div>

      <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
        <label class="block">
          <span class="mb-1.5 block text-xs font-medium text-zinc-400">일반 사용자 최대 세션 수</span>
          <input v-model.number="form.max_sessions_user" min="1" type="number" class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50" />
        </label>
        <label class="block">
          <span class="mb-1.5 block text-xs font-medium text-zinc-400">관리자 최대 세션 수</span>
          <input v-model.number="form.max_sessions_staff" min="1" type="number" class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50" />
        </label>
        <label class="block">
          <span class="mb-1.5 block text-xs font-medium text-zinc-400">유휴 timeout(분)</span>
          <input v-model.number="form.idle_timeout_minutes" min="1" type="number" class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50" />
        </label>
        <label class="block">
          <span class="mb-1.5 block text-xs font-medium text-zinc-400">절대 timeout(시간)</span>
          <input v-model.number="form.absolute_timeout_hours" min="1" type="number" class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50" />
        </label>
        <label class="block md:col-span-2">
          <span class="mb-1.5 block text-xs font-medium text-zinc-400">세션 한도 도달 시</span>
          <AppSelect
            v-model="form.on_session_limit"
            :options="[
              { value: 'revoke_oldest', label: '가장 오래된 세션 종료 후 로그인 허용' },
              { value: 'block_new', label: '새 로그인 차단' }
            ]"
          />
        </label>
        <label class="flex items-center gap-3 text-sm font-medium text-zinc-400">
          <input v-model="form.revoke_sessions_on_permission_change" type="checkbox" class="h-4 w-4 rounded border-zinc-600 bg-zinc-800 accent-indigo-500" />
          권한 변경 시 기존 세션 종료
        </label>
        <label class="flex items-center gap-3 text-sm font-medium text-zinc-400">
          <input v-model="form.block_inactive_user_login" type="checkbox" class="h-4 w-4 rounded border-zinc-600 bg-zinc-800 accent-indigo-500" />
          비활성 사용자 로그인 차단
        </label>
      </div>

      <div v-if="error" class="mt-5 rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2.5 text-sm text-red-400">{{ error }}</div>
      <div v-if="message" class="mt-5 rounded-lg border border-emerald-500/20 bg-emerald-500/10 px-3 py-2.5 text-sm text-emerald-400">{{ message }}</div>

      <footer class="mt-6 flex justify-end border-t border-zinc-800 pt-4">
        <button class="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-indigo-500 disabled:opacity-50" :disabled="saving" type="submit">
          {{ saving ? '저장 중...' : '설정 저장' }}
        </button>
      </footer>
    </form>
  </div>
</template>
