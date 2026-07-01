<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { XIcon } from 'lucide-vue-next'
import { AppUser, AppUserPayload, ScreenDefinition } from '../../composables/useApi'

const props = defineProps<{
  user: AppUser | null
  screens: ScreenDefinition[]
}>()

const emit = defineEmits<{
  close: []
  save: [payload: AppUserPayload]
  delete: [user: AppUser]
}>()

const isEdit = computed(() => Boolean(props.user))
const form = reactive<AppUserPayload>({
  username: '',
  password: '',
  is_staff: false,
  is_active: true,
  allowed_screens: ['dashboard', 'playground']
})

watch(
  () => props.user,
  (user) => {
    Object.assign(form, {
      username: user?.username ?? '',
      password: '',
      is_staff: user?.is_staff ?? false,
      is_active: user?.is_active ?? true,
      allowed_screens: user?.allowed_screens ?? ['dashboard', 'playground']
    })
  },
  { immediate: true }
)

const customScreens = computed(() =>
  form.allowed_screens.filter((screen) => !props.screens.some((option) => option.id === screen))
)

function removeScreen(screen: string) {
  form.allowed_screens = form.allowed_screens.filter((selected) => selected !== screen)
}
</script>

<template>
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm" @click="emit('close')">
    <div class="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-xl border border-zinc-800 bg-zinc-900 shadow-2xl animate-fade-in" @click.stop>
      <header class="flex items-center justify-between border-b border-zinc-800 px-6 py-5">
        <div>
          <p class="mb-1 text-xs font-semibold uppercase tracking-widest text-indigo-400">사용자</p>
          <h3 class="text-lg font-semibold text-zinc-100">{{ isEdit ? '사용자 상세' : '새 사용자' }}</h3>
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
        <div class="mb-5 grid grid-cols-1 gap-4 md:grid-cols-2">
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">사용자명</span>
            <input v-model="form.username" required class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50" />
          </label>
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">비밀번호</span>
            <input
              v-model="form.password"
              :required="!isEdit"
              type="password"
              placeholder="비워두면 현재 비밀번호 유지"
              class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 placeholder-zinc-600 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50"
            />
          </label>
          <label class="flex items-center gap-3 text-sm font-medium text-zinc-400">
            <input v-model="form.is_staff" type="checkbox" class="h-4 w-4 rounded border-zinc-600 bg-zinc-800 accent-indigo-500" />
            관리자 사용자
          </label>
          <label class="flex items-center gap-3 text-sm font-medium text-zinc-400">
            <input v-model="form.is_active" type="checkbox" class="h-4 w-4 rounded border-zinc-600 bg-zinc-800 accent-indigo-500" />
            활성
          </label>
        </div>

        <!-- Screen permissions -->
        <div class="mb-5 rounded-lg border border-zinc-800 bg-zinc-800/40 p-4">
          <div class="mb-3 flex items-center justify-between gap-3">
            <p class="text-xs font-semibold uppercase tracking-wide text-zinc-400">허용 화면</p>
            <span class="rounded-md bg-zinc-700 px-2 py-0.5 text-xs font-medium text-zinc-300">{{ form.allowed_screens.length }}개 선택</span>
          </div>
          <div class="grid grid-cols-1 gap-1.5 md:grid-cols-2">
            <label
              v-for="screen in screens"
              :key="screen.id"
              class="flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2 text-sm transition hover:bg-zinc-700/50"
              :class="{ 'opacity-50': !screen.is_active && !form.allowed_screens.includes(screen.id) }"
            >
              <input
                v-model="form.allowed_screens"
                :value="screen.id"
                :disabled="!screen.is_active && !form.allowed_screens.includes(screen.id)"
                type="checkbox"
                class="h-4 w-4 rounded border-zinc-600 bg-zinc-800 accent-indigo-500 disabled:opacity-40"
              />
              <span>
                <span class="font-medium text-zinc-200">{{ screen.label }}</span>
                <span class="ml-2 text-xs text-zinc-500">{{ screen.id }}</span>
                <span v-if="!screen.is_active" class="ml-2 rounded-md bg-zinc-700 px-1.5 py-0.5 text-xs text-zinc-500">비활성</span>
              </span>
            </label>
          </div>
          <div v-if="customScreens.length" class="mt-3 flex flex-wrap gap-2">
            <span
              v-for="screen in customScreens"
              :key="screen"
              class="inline-flex items-center gap-1.5 rounded-md border border-zinc-700 bg-zinc-800 px-2.5 py-1 text-xs font-medium text-zinc-300"
            >
              {{ screen }}
              <button class="text-zinc-500 hover:text-red-400 transition-colors" type="button" @click="removeScreen(screen)">
                <XIcon class="h-3 w-3" />
              </button>
            </span>
          </div>
        </div>

        <footer class="flex items-center gap-3 border-t border-zinc-800 pt-4">
          <button
            v-if="user"
            class="rounded-lg border border-red-500/30 px-4 py-2 text-sm font-medium text-red-400 transition-colors hover:bg-red-500/10"
            type="button"
            @click="emit('delete', user)"
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
          <button class="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-indigo-500" type="submit">
            {{ isEdit ? '변경사항 저장' : '사용자 생성' }}
          </button>
        </footer>
      </form>
    </div>
  </div>
</template>
