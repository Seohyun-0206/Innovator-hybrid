<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ArchiveIcon } from 'lucide-vue-next'
import AppSelect, { SelectOption } from '../components/common/AppSelect.vue'
import MarkdownViewer from '../components/common/MarkdownViewer.vue'
import { EvaluationArtifacts, EvaluationResult, useApi } from '../composables/useApi'

const api = useApi()
const results = ref<EvaluationResult[]>([])
const selectedResult = ref('')
const artifacts = ref<EvaluationArtifacts | null>(null)
const loading = ref(false)
const error = ref('')

const resultOptions = computed<SelectOption[]>(() => [
  { value: '', label: '결과 선택' },
  ...results.value.map((result) => ({
    value: String(result.id),
    label: `${result.run_name} · ${result.model_display_name} · ${result.status}`,
  })),
])

async function loadResults() {
  results.value = await api.getEvaluationResults()
  const firstCompleted = results.value.find((result) => result.status === 'completed') ?? results.value[0]
  if (!selectedResult.value && firstCompleted) {
    selectedResult.value = String(firstCompleted.id)
  }
}

async function loadArtifacts() {
  artifacts.value = null
  error.value = ''
  if (!selectedResult.value) {
    return
  }
  loading.value = true
  try {
    artifacts.value = await api.getEvaluationArtifacts(Number(selectedResult.value))
  } catch (err) {
    error.value = err instanceof Error ? err.message : '산출물을 불러오지 못했습니다.'
  } finally {
    loading.value = false
  }
}

function formatJson(value: unknown) {
  return JSON.stringify(value, null, 2)
}

watch(selectedResult, loadArtifacts)

onMounted(async () => {
  await loadResults()
  await loadArtifacts()
})
</script>

<template>
  <div class="page-shell">
    <div class="page-header">
      <div>
        <p class="page-label">실험</p>
        <h2 class="page-title">산출물</h2>
        <p class="page-subtitle">실험 결과를 manifest, summary, scorecard, JSONL-like 로그, report markdown 형태로 확인합니다.</p>
      </div>
      <div class="min-w-80">
        <AppSelect v-model="selectedResult" :options="resultOptions" />
      </div>
    </div>

    <div v-if="error" class="alert-error mb-4">{{ error }}</div>
    <div v-if="loading" class="section-card p-6 text-sm text-zinc-500">산출물을 생성하는 중...</div>

    <div v-else-if="artifacts" class="space-y-5">
      <section class="grid gap-5 xl:grid-cols-2">
        <div class="section-card-padded">
          <h3 class="mb-3 font-semibold text-zinc-100">eval_manifest</h3>
          <pre class="code-panel max-h-96">{{ formatJson(artifacts.eval_manifest) }}</pre>
        </div>
        <div class="section-card-padded">
          <h3 class="mb-3 font-semibold text-zinc-100">model_summary</h3>
          <pre class="code-panel max-h-96">{{ formatJson(artifacts.model_summary) }}</pre>
        </div>
      </section>

      <section class="grid gap-5 xl:grid-cols-2">
        <div class="section-card-padded">
          <h3 class="mb-3 font-semibold text-zinc-100">scorecard</h3>
          <pre class="code-panel max-h-96">{{ formatJson(artifacts.scorecard) }}</pre>
        </div>
        <div class="section-card-padded">
          <h3 class="mb-3 font-semibold text-zinc-100">jsonl-like logs</h3>
          <pre class="code-panel max-h-96">{{ artifacts.jsonl_like_logs.map((row) => JSON.stringify(row)).join('\n') }}</pre>
        </div>
      </section>

      <section class="section-card-padded">
        <h3 class="mb-3 font-semibold text-zinc-100">report markdown</h3>
        <MarkdownViewer :content="artifacts.report_markdown" />
      </section>
    </div>

    <div v-else class="section-card p-10 text-center">
      <ArchiveIcon class="empty-icon" />
      <h3 class="empty-title">선택 가능한 평가 결과가 없습니다</h3>
      <p class="empty-description">실험을 생성하고 실행하면 산출물이 API에서 생성됩니다.</p>
    </div>
  </div>
</template>
