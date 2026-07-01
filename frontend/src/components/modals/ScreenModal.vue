<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { XIcon } from 'lucide-vue-next'
import { ScreenDefinition, ScreenDefinitionPayload } from '../../composables/useApi'

const props = defineProps<{
  screen: ScreenDefinition | null
}>()

const emit = defineEmits<{
  close: []
  save: [payload: ScreenDefinitionPayload]
  delete: [screen: ScreenDefinition]
}>()

const isEdit = computed(() => Boolean(props.screen))
const form = reactive<ScreenDefinitionPayload>({
  id: '',
  label: '',
  description: '',
  sort_order: 100,
  is_active: true
})

watch(
  () => props.screen,
  (screen) => {
    Object.assign(form, {
      id: screen?.id ?? '',
      label: screen?.label ?? '',
      description: screen?.description ?? '',
      sort_order: screen?.sort_order ?? 100,
      is_active: screen?.is_active ?? true
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
          <p class="mb-1 text-xs font-semibold uppercase tracking-widest text-indigo-400">화면 권한</p>
          <h3 class="text-lg font-semibold text-zinc-100">{{ isEdit ? '화면 상세' : '새 화면' }}</h3>
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
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">화면 ID</span>
            <input v-model="form.id" required pattern="[a-z0-9_-]+" placeholder="reports" class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 placeholder-zinc-600 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50" />
          </label>
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">화면명</span>
            <input v-model="form.label" required placeholder="보고서" class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 placeholder-zinc-600 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50" />
          </label>
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-zinc-400">정렬 순서</span>
            <input v-model.number="form.sort_order" required type="number" min="0" class="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50" />
          </label>
          <label class="flex items-center gap-3 pt-6 text-sm font-medium text-zinc-400">
            <input v-model="form.is_active" type="checkbox" class="h-4 w-4 rounded border-zinc-600 bg-zinc-800 accent-indigo-500" />
            활성
          </label>
        </div>

        <label class="mb-5 block">
          <span class="mb-1.5 block text-xs font-medium text-zinc-400">설명</span>
          <textarea
            v-model="form.description"
            class="min-h-28 w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2.5 text-sm text-zinc-200 placeholder-zinc-600 outline-none transition focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50 resize-vertical"
            placeholder="이 화면이 표시되는 위치 또는 제어하는 권한을 입력하세요."
          />
        </label>

        <footer class="flex items-center gap-3 border-t border-zinc-800 pt-4">
          <button
            v-if="screen"
            class="rounded-lg border border-red-500/30 px-4 py-2 text-sm font-medium text-red-400 transition-colors hover:bg-red-500/10"
            type="button"
            @click="emit('delete', screen)"
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
            {{ isEdit ? '변경사항 저장' : '화면 생성' }}
          </button>
        </footer>
      </form>
    </div>
  </div>
</template>
