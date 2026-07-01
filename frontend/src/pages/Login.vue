<script setup lang="ts">
import { ref } from 'vue'
import { BotIcon, LockIcon, UserIcon } from 'lucide-vue-next'
import { LoginResponse, useApi } from '../composables/useApi'

const emit = defineEmits<{
  loggedIn: [response: LoginResponse]
}>()

const api = useApi()
const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function submit() {
  loading.value = true
  error.value = ''
  try {
    const response = await api.login(username.value, password.value)
    emit('loggedIn', response)
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Login failed'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="flex min-h-screen items-center justify-center bg-zinc-950 p-6">
    <div class="w-full max-w-sm animate-fade-in">
      <!-- Logo -->
      <div class="mb-8 flex flex-col items-center gap-3">
        <div class="flex h-12 w-12 items-center justify-center rounded-xl bg-indigo-600 shadow-lg shadow-indigo-500/20">
          <BotIcon class="h-6 w-6 text-white" />
        </div>
        <div class="text-center">
          <p class="text-xs font-semibold uppercase tracking-widest text-zinc-500">LLM Policy Gateway</p>
          <h1 class="mt-1 text-xl font-bold text-zinc-100">Routing Admin</h1>
        </div>
      </div>

      <!-- Card -->
      <div class="rounded-xl border border-zinc-800 bg-zinc-900 p-6 shadow-2xl">
        <h2 class="mb-5 text-sm font-semibold text-zinc-300">Sign in to your account</h2>

        <!-- Error -->
        <div
          v-if="error"
          class="mb-4 flex items-start gap-2 rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2.5 text-sm text-red-400"
        >
          {{ error }}
        </div>

        <form @submit.prevent="submit" class="space-y-4">
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">Username</span>
            <div class="relative">
              <UserIcon class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
              <input
                v-model="username"
                required
                autocomplete="username"
                class="w-full rounded-lg border border-zinc-700 bg-zinc-800 py-2.5 pl-9 pr-3 text-sm text-zinc-100 placeholder-zinc-600 outline-none ring-0 transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50"
                placeholder="Enter username"
              />
            </div>
          </label>

          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">Password</span>
            <div class="relative">
              <LockIcon class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
              <input
                v-model="password"
                required
                type="password"
                autocomplete="current-password"
                class="w-full rounded-lg border border-zinc-700 bg-zinc-800 py-2.5 pl-9 pr-3 text-sm text-zinc-100 placeholder-zinc-600 outline-none ring-0 transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50"
                placeholder="Enter password"
              />
            </div>
          </label>

          <button
            class="mt-2 flex w-full items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-indigo-500/20 transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="loading"
            type="submit"
          >
            <div v-if="loading" class="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white"></div>
            {{ loading ? 'Signing in...' : 'Sign in' }}
          </button>
        </form>
      </div>
    </div>
  </main>
</template>
