<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { CheckIcon, ChevronDownIcon } from 'lucide-vue-next'

export interface SelectOption {
  value: string
  label: string
}

const props = defineProps<{
  modelValue: string
  options: (SelectOption | string)[]
  placeholder?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const open = ref(false)
const containerRef = ref<HTMLDivElement | null>(null)

const normalizedOptions = computed<SelectOption[]>(() =>
  props.options.map((opt) =>
    typeof opt === 'string' ? { value: opt, label: opt } : opt
  )
)

const selectedLabel = computed(
  () =>
    normalizedOptions.value.find((o) => o.value === props.modelValue)?.label ??
    props.placeholder ??
    props.modelValue
)

function select(value: string) {
  emit('update:modelValue', value)
  open.value = false
}

function handleDocumentClick(e: MouseEvent) {
  if (containerRef.value && !containerRef.value.contains(e.target as Node)) {
    open.value = false
  }
}

onMounted(() => document.addEventListener('click', handleDocumentClick))
onBeforeUnmount(() => document.removeEventListener('click', handleDocumentClick))
</script>

<template>
  <div ref="containerRef" class="relative">
    <button
      type="button"
      class="ui-input flex items-center justify-between gap-2 hover:border-zinc-600"
      @click="open = !open"
    >
      <span class="truncate">{{ selectedLabel }}</span>
      <ChevronDownIcon
        class="h-4 w-4 shrink-0 text-zinc-500 transition-transform duration-150"
        :class="{ 'rotate-180': open }"
      />
    </button>

    <Transition
      enter-active-class="transition duration-100 ease-out"
      enter-from-class="opacity-0 scale-95 -translate-y-1"
      enter-to-class="opacity-100 scale-100 translate-y-0"
      leave-active-class="transition duration-75 ease-in"
      leave-from-class="opacity-100 scale-100 translate-y-0"
      leave-to-class="opacity-0 scale-95 -translate-y-1"
    >
      <div
        v-if="open"
        class="absolute left-0 top-full z-50 mt-1 min-w-full rounded-lg border border-zinc-700 bg-zinc-800 py-1 shadow-xl shadow-black/40"
      >
        <button
          v-for="option in normalizedOptions"
          :key="option.value"
          type="button"
          class="select-option"
          :class="option.value === modelValue ? 'select-option-selected' : ''"
          @click="select(option.value)"
        >
          <CheckIcon v-if="option.value === modelValue" class="h-4 w-4 shrink-0 text-indigo-400" />
          <span v-else class="h-4 w-4 shrink-0" />
          {{ option.label }}
        </button>
      </div>
    </Transition>
  </div>
</template>
