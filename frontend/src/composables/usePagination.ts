import { computed, ref, unref, watch, type ComputedRef, type Ref } from 'vue'

type PaginationSource<T> = Ref<T[]> | ComputedRef<T[]>

export function usePagination<T>(items: PaginationSource<T>, initialPageSize = 10, options = [5, 10, 25, 50]) {
  const page = ref(1)
  const pageSize = ref(initialPageSize)
  const pageSizeOptions = options

  const totalItems = computed(() => unref(items).length)
  const totalPages = computed(() => Math.max(1, Math.ceil(totalItems.value / pageSize.value)))
  const startItem = computed(() => (totalItems.value === 0 ? 0 : (page.value - 1) * pageSize.value + 1))
  const endItem = computed(() => Math.min(page.value * pageSize.value, totalItems.value))
  const paginatedItems = computed(() => {
    const startIndex = (page.value - 1) * pageSize.value
    return unref(items).slice(startIndex, startIndex + pageSize.value)
  })

  watch(items, () => {
    page.value = 1
  })

  watch([page, pageSize, totalItems], () => {
    if (page.value > totalPages.value) {
      page.value = totalPages.value
    }
  })

  watch(pageSize, () => {
    page.value = 1
  })

  return {
    page,
    pageSize,
    pageSizeOptions,
    totalItems,
    totalPages,
    startItem,
    endItem,
    paginatedItems
  }
}
