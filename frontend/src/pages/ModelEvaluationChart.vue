<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import {
  BarChart3,
  Check,
  FlaskConical,
  RefreshCw,
  Search,
} from "lucide-vue-next";
import { EvaluationResult, EvaluationRun, useApi } from "../composables/useApi";
import ExperimentModelDetail from "./ExperimentModelDetail.vue";

const api = useApi();
const runs = ref<EvaluationRun[]>([]);
const results = ref<EvaluationResult[]>([]);
const selectedIds = ref<number[]>([]);
const query = ref("");
const loading = ref(false);
const error = ref("");
const selectedMetricKeys = ref<string[]>(["accuracy", "latency", "failure"]);
const sortKey = ref("accuracy");
const sortDirection = ref<"asc" | "desc">("desc");
const detailRunId = ref<number | null>(null);
const palette = [
  "#60a5fa",
  "#34d399",
  "#fbbf24",
  "#c084fc",
  "#fb7185",
  "#22d3ee",
  "#f97316",
  "#a3e635",
];

const sortedRuns = computed(() =>
  [...runs.value].sort(
    (a, b) => +new Date(b.created_at) - +new Date(a.created_at),
  ),
);
const filteredRuns = computed(() => {
  const q = query.value.trim().toLowerCase();
  return sortedRuns.value.filter(
    (run) =>
      !q ||
      `${run.name} ${run.dataset_name} ${run.status}`.toLowerCase().includes(q),
  );
});
const selectedRuns = computed(
  () =>
    selectedIds.value
      .map((id) => runs.value.find((r) => r.id === id))
      .filter(Boolean) as EvaluationRun[],
);
const comparisonIssues = computed(() => {
  if (selectedRuns.value.length < 2) return [];
  const issues: string[] = [];
  if (new Set(selectedRuns.value.map((run) => run.dataset)).size > 1)
    issues.push("데이터셋");
  if (
    new Set(selectedRuns.value.map((run) => run.dataset_question_count)).size >
    1
  )
    issues.push("문항 수");
  if (new Set(selectedRuns.value.map((run) => run.evaluation_method)).size > 1)
    issues.push("평가 방식");
  return issues;
});
const completedFor = (id: number) => {
  const run = runs.value.find((r) => r.id === id);
  const embedded = run?.results ?? [];
  return (
    embedded.length ? embedded : results.value.filter((r) => r.run === id)
  ).filter((r) => r.status === "completed");
};
const number = (value: unknown) =>
  value === null || value === "" || !Number.isFinite(Number(value))
    ? null
    : Number(value);
const avg = (values: (number | null)[]) => {
  const valid = values.filter((v): v is number => v !== null);
  return valid.length ? valid.reduce((a, b) => a + b, 0) / valid.length : null;
};
const weightedAvg = (
  rows: EvaluationResult[],
  getter: (row: EvaluationResult) => number | null,
) => {
  const valid = rows
    .map((row) => ({
      value: getter(row),
      weight: row.item_result_count > 0 ? row.item_result_count : 1,
    }))
    .filter((item) => item.value !== null);
  const total = valid.reduce((sum, item) => sum + item.weight, 0);
  return total
    ? valid.reduce(
        (sum, item) => sum + (item.value as number) * item.weight,
        0,
      ) / total
    : null;
};
const summaries = computed(() =>
  selectedRuns.value.map((run, index) => {
    const rows = completedFor(run.id);
    const config = run.config ?? {};
    return {
      run,
      rows,
      color: palette[index % palette.length],
      order: index + 1,
      sampleCount: rows.reduce(
        (sum, row) => sum + Math.max(row.item_result_count || 0, 0),
        0,
      ),
      accuracy: weightedAvg(rows, (r) => number(r.overall_accuracy)),
      strict: weightedAvg(rows, (r) => number(r.strict_compliance_rate)),
      parseFailure: weightedAvg(rows, (r) => number(r.parse_failure_rate)),
      latency: avg(rows.map((r) => number(r.latency_p95_ms))),
      ttft: avg(rows.map((r) => number(r.ttft_p95_ms))),
      tpot: avg(rows.map((r) => number(r.tpot_p95_ms))),
      throughput: avg(rows.map((r) => number(r.system_throughput_tps))),
      kvCache: avg(rows.map((r) => number(r.kv_cache_usage_avg))),
      failure: weightedAvg(rows, (r) => number(r.failure_rate)),
      tokens: rows.reduce(
        (s, r) => s + (r.input_tokens || 0) + (r.output_tokens || 0),
        0,
      ),
      cost: rows.some((r) => number(r.estimated_cost_usd) !== null)
        ? rows.reduce((s, r) => s + (number(r.estimated_cost_usd) ?? 0), 0)
        : null,
      concurrency: config.concurrency ?? parseName(run.name).concurrency,
      ratio: parseName(run.name).ratio,
      mode: /^routing/i.test(run.name)
        ? "Routing"
        : /^single/i.test(run.name)
          ? "Single"
          : "-",
      version: /_v(\d+)/i.exec(run.name)?.[1]
        ? `v${/_v(\d+)/i.exec(run.name)?.[1]}`
        : "v1",
    };
  }),
);
const metrics = computed(() => [
  {
    key: "accuracy",
    label: "평균 정확도",
    better: "높을수록 좋음",
    format: (v: number | null) => percent(v),
    max: 1,
  },
  {
    key: "latency",
    label: "후보별 p95 평균",
    better: "낮을수록 좋음",
    format: (v: number | null) =>
      v === null ? "-" : `${Math.round(v).toLocaleString()} ms`,
    max: Math.max(...summaries.value.map((s) => s.latency ?? 0), 1),
  },
  {
    key: "failure",
    label: "평균 실패율",
    better: "낮을수록 좋음",
    format: (v: number | null) => percent(v),
    max: Math.max(...summaries.value.map((s) => s.failure ?? 0), 0.01),
  },
  {
    key: "strict",
    label: "Strict 준수율",
    better: "높을수록 좋음",
    format: (v: number | null) => percent(v),
    max: 1,
  },
  {
    key: "parseFailure",
    label: "Parse 실패율",
    better: "낮을수록 좋음",
    format: (v: number | null) => percent(v),
    max: Math.max(...summaries.value.map((s) => s.parseFailure ?? 0), 0.01),
  },
  {
    key: "ttft",
    label: "TTFT p95 평균",
    better: "낮을수록 좋음",
    format: formatMs,
    max: Math.max(...summaries.value.map((s) => s.ttft ?? 0), 1),
  },
  {
    key: "tpot",
    label: "TPOT p95 평균",
    better: "낮을수록 좋음",
    format: formatMs,
    max: Math.max(...summaries.value.map((s) => s.tpot ?? 0), 1),
  },
  {
    key: "throughput",
    label: "System Throughput",
    better: "높을수록 좋음",
    format: (v: number | null) => (v === null ? "-" : `${v.toFixed(1)} tok/s`),
    max: Math.max(...summaries.value.map((s) => s.throughput ?? 0), 1),
  },
  {
    key: "tokens",
    label: "토큰 합계",
    better: "낮을수록 좋음",
    format: (v: number | null) =>
      v === null ? "-" : `${Math.round(v).toLocaleString()} tok`,
    max: Math.max(...summaries.value.map((s) => s.tokens), 1),
  },
  {
    key: "cost",
    label: "추정 비용 합계",
    better: "낮을수록 좋음",
    format: (v: number | null) => (v === null ? "-" : `$${v.toFixed(5)}`),
    max: Math.max(...summaries.value.map((s) => s.cost ?? 0), 0.00001),
  },
  {
    key: "kvCache",
    label: "KV Cache 사용률",
    better: "환경과 함께 해석",
    format: (v: number | null) => percent(v),
    max: 1,
  },
]);
const selectedMetrics = computed(() =>
  metrics.value.filter((metric) =>
    selectedMetricKeys.value.includes(metric.key),
  ),
);
const detailSummary = computed(
  () =>
    summaries.value.find((item) => item.run.id === detailRunId.value) ?? null,
);
const chartGridStyle = computed(() => ({
  gridTemplateColumns: `repeat(${Math.min(selectedMetrics.value.length, 3)}, minmax(0, 1fr))`,
  gridAutoRows: "250px",
}));
const detailRows = computed(() =>
  summaries.value.flatMap((item) => item.rows.map((row) => ({ item, row }))),
);
const sortedDetailRows = computed(() => {
  const value = (entry: (typeof detailRows.value)[number]): string | number => {
    if (sortKey.value === "experiment") return entry.item.run.name;
    if (sortKey.value === "candidate")
      return (
        entry.row.candidate_label ||
        entry.row.model_display_name ||
        entry.row.model_name ||
        ""
      );
    if (sortKey.value === "accuracy")
      return number(entry.row.overall_accuracy) ?? -Infinity;
    if (sortKey.value === "latency")
      return number(entry.row.latency_p95_ms) ?? -Infinity;
    if (sortKey.value === "failure")
      return number(entry.row.failure_rate) ?? -Infinity;
    if (sortKey.value === "tokens")
      return (entry.row.input_tokens || 0) + (entry.row.output_tokens || 0);
    return number(entry.row.estimated_cost_usd) ?? -Infinity;
  };
  return [...detailRows.value].sort((a, b) => {
    const av = value(a),
      bv = value(b);
    const result =
      typeof av === "string" && typeof bv === "string"
        ? av.localeCompare(bv)
        : Number(av) - Number(bv);
    return sortDirection.value === "asc" ? result : -result;
  });
});

function parseName(name: string) {
  const match = /E(\d+)-H(\d+)_C(\d+)/i.exec(name);
  return {
    ratio: match ? `${match[1]}:${match[2]}` : "-",
    concurrency: match?.[3] ?? "-",
  };
}
function percent(value: number | null) {
  return value === null ? "-" : `${(value * 100).toFixed(1)}%`;
}
function formatMs(value: number | null) {
  return value === null ? "-" : `${Math.round(value).toLocaleString()} ms`;
}
function sortBy(key: string) {
  if (sortKey.value === key)
    sortDirection.value = sortDirection.value === "asc" ? "desc" : "asc";
  else {
    sortKey.value = key;
    sortDirection.value = "desc";
  }
}
function sortMark(key: string) {
  return sortKey.value === key
    ? sortDirection.value === "asc"
      ? "↑"
      : "↓"
    : "↕";
}
function toggleMetric(key: string) {
  if (selectedMetricKeys.value.includes(key)) {
    if (selectedMetricKeys.value.length > 1)
      selectedMetricKeys.value = selectedMetricKeys.value.filter(
        (value) => value !== key,
      );
  } else selectedMetricKeys.value = [...selectedMetricKeys.value, key];
}
function toggle(id: number) {
  if (selectedIds.value.includes(id))
    selectedIds.value = selectedIds.value.filter((v) => v !== id);
  else selectedIds.value = [...selectedIds.value, id];
}
function openExperimentDetail(id: number) {
  sessionStorage.setItem("selected-evaluation-run-id", String(id));
  detailRunId.value = id;
}
function width(value: number | null, max: number) {
  return value === null || value === 0
    ? "0%"
    : `${Math.max(2, (value / max) * 100)}%`;
}
function metricDomain(key: string) {
  const values = summaries.value
    .map((item) => metricValue(item, key))
    .filter((value): value is number => value !== null);
  if (!values.length) return { min: 0, max: 1 };
  const rawMin = Math.min(...values),
    rawMax = Math.max(...values);
  const baseRange = Math.max(
    rawMax - rawMin,
    Math.max(Math.abs(rawMax), 1) * 0.02,
  );
  const center = (rawMin + rawMax) / 2;
  const range = baseRange * 1.3;
  return { min: center - range / 2, max: center + range / 2 };
}
function chartHeight(value: number | null, key: string) {
  if (value === null || value === 0) return "0%";
  const domain = metricDomain(key);
  return `${Math.max(3, Math.min(100, ((value - domain.min) / Math.max(domain.max - domain.min, Number.EPSILON)) * 100))}%`;
}
function formatAxis(
  value: number,
  metric: { format: (value: number | null) => string },
) {
  return metric.format(value);
}
function formatDate(value: string | null) {
  return value
    ? new Intl.DateTimeFormat("ko-KR", {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(new Date(value))
    : "-";
}
function metricValue(item: unknown, key: string): number | null {
  return number((item as Record<string, unknown>)[key]);
}
function delta(value: number | null, key: string) {
  const baseline = summaries.value[0]
    ? metricValue(summaries.value[0], key)
    : null;
  if (value === null || baseline === null) return "-";
  const difference = value - baseline;
  if (
    ["accuracy", "failure", "strict", "parseFailure", "kvCache"].includes(key)
  )
    return `${difference > 0 ? "+" : ""}${(difference * 100).toFixed(1)}%p`;
  return `${difference > 0 ? "+" : ""}${Math.round(difference).toLocaleString()} ms`;
}
async function load() {
  loading.value = true;
  error.value = "";
  try {
    const [runData, resultData] = await Promise.all([
      api.getEvaluationRuns(),
      api.getEvaluationResults(),
    ]);
    runs.value = runData;
    results.value = resultData;
    const available = new Set(runData.map((run) => run.id));
    const preserved = selectedIds.value.filter((id) => available.has(id));
    selectedIds.value = preserved.length
      ? preserved
      : [...runData]
          .filter((r) => r.status === "completed")
          .sort((a, b) => +new Date(b.created_at) - +new Date(a.created_at))
          .slice(0, 3)
          .map((r) => r.id);
  } catch (e) {
    error.value =
      e instanceof Error ? e.message : "데이터를 불러오지 못했습니다.";
  } finally {
    loading.value = false;
  }
}
onMounted(load);
</script>

<template>
  <main
    data-testid="experiment-comparison-page"
    class="space-y-6 p-4 text-slate-100 md:p-7"
    :aria-busy="loading"
  >
    <header class="flex flex-wrap items-start justify-between gap-4">
      <div>
        <p class="text-sm font-medium text-blue-400">MODEL EVALUATION</p>
        <h1 class="mt-1 text-2xl font-bold">실험 비교</h1>
        <p class="mt-2 text-sm text-slate-400">
          동일한 기준으로 선택한 실험의 품질, 속도, 비용을 차트 중심으로
          비교합니다.
        </p>
      </div>
      <button
        class="flex items-center gap-2 rounded-lg border border-slate-700 px-3 py-2 text-sm hover:bg-slate-800"
        :disabled="loading"
        @click="load"
      >
        <RefreshCw
          class="h-4 w-4"
          :class="{ 'animate-spin': loading }"
        />새로고침
      </button>
    </header>

    <p
      v-if="error"
      role="alert"
      class="rounded-lg border border-red-800 bg-red-950/40 p-3 text-sm text-red-300"
    >
      {{ error }}
    </p>
    <section class="grid gap-5 xl:grid-cols-[320px_minmax(0,1fr)]">
      <aside
        class="rounded-xl border border-slate-800 bg-slate-900/60 p-4 xl:sticky xl:top-4 xl:self-start"
      >
        <div class="mb-3 flex items-center justify-between">
          <h2 class="font-semibold">비교할 실험</h2>
          <div class="flex items-center gap-2">
            <button
              v-if="selectedIds.length"
              class="text-xs text-slate-400 underline hover:text-white"
              type="button"
              @click="selectedIds = []"
            >
              전체 해제</button
            ><output aria-live="polite" class="text-sm text-slate-400"
              >{{ selectedIds.length }}개 선택</output
            >
          </div>
        </div>
        <p
          id="experiment-limit-message"
          class="mb-3 text-xs text-slate-500"
          role="status"
        >
          완료된 실험을 제한 없이 선택할 수 있습니다.
        </p>
        <label class="relative block"
          ><span class="sr-only">실험 검색</span
          ><Search
            class="absolute left-3 top-2.5 h-4 w-4 text-slate-500" /><input
            v-model="query"
            class="w-full rounded-lg border border-slate-700 bg-slate-950 py-2 pl-9 pr-3 text-sm outline-none focus:border-blue-500"
            placeholder="실험명 또는 데이터셋 검색"
        /></label>
        <div class="mt-3 max-h-[540px] space-y-2 overflow-auto pr-1">
          <button
            v-for="run in filteredRuns"
            :key="run.id"
            class="flex w-full items-start gap-3 rounded-lg border p-3 text-left transition"
            :class="
              selectedIds.includes(run.id)
                ? 'border-blue-500 bg-blue-500/10'
                : 'border-slate-800 hover:border-slate-600 disabled:opacity-40'
            "
            :disabled="run.status !== 'completed'"
            :aria-pressed="selectedIds.includes(run.id)"
            @click="toggle(run.id)"
          >
            <span
              class="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded border"
              :class="
                selectedIds.includes(run.id)
                  ? 'border-blue-500 bg-blue-500'
                  : 'border-slate-600'
              "
              ><Check v-if="selectedIds.includes(run.id)" class="h-3.5 w-3.5"
            /></span>
            <span class="min-w-0"
              ><span class="block truncate text-sm font-medium">{{
                run.name
              }}</span
              ><span class="mt-1 block truncate text-xs text-slate-500"
                >{{ run.dataset_name }} · {{ run.status }}</span
              ></span
            >
          </button>
        </div>
        <p
          v-if="!filteredRuns.length"
          class="mt-4 text-center text-sm text-slate-500"
        >
          검색 결과가 없습니다.
        </p>
      </aside>

      <div v-if="summaries.length" class="min-w-0 space-y-5">
        <div
          v-if="comparisonIssues.length"
          role="alert"
          class="rounded-xl border border-amber-700/60 bg-amber-950/30 p-4 text-sm text-amber-200"
        >
          <strong>비교 조건이 다릅니다.</strong>
          {{ comparisonIssues.join(", ") }}이(가) 달라 증감을 직접적인 우열로
          해석하지 마세요.
        </div>
        <div
          class="rounded-xl border border-blue-800/50 bg-blue-950/20 p-4 text-xs text-blue-200"
        >
          정확도·실패율은 문항 수 가중 평균, p95는 후보별 p95 산술평균,
          토큰·비용은 완료 후보 합계입니다. 후보 수가 다른 실험은 해석에
          주의하세요. 첫 번째 실험이 Δ 기준입니다.
        </div>
        <section
          class="grid gap-3 sm:grid-cols-2 2xl:grid-cols-5"
          aria-label="선택 실험 요약"
        >
          <button
            v-for="item in summaries"
            :key="item.run.id"
            type="button"
            class="rounded-xl border border-slate-800 bg-slate-900/60 p-4 text-left transition hover:-translate-y-0.5 hover:border-slate-600 hover:bg-slate-800/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
            :style="{ borderTopColor: item.color, borderTopWidth: '3px' }"
            @click="openExperimentDetail(item.run.id)"
          >
            <p class="truncate text-sm font-semibold" :title="item.run.name">
              #{{ item.order }} {{ item.run.name }}
            </p>
            <p class="mt-3 text-2xl font-bold">{{ percent(item.accuracy) }}</p>
            <p class="text-xs text-slate-500">
              문항 수 가중 정확도 · 후보 {{ item.rows.length }}개 · 표본
              {{ item.sampleCount.toLocaleString() }}
            </p>
            <div class="mt-3 flex justify-between text-xs text-slate-400">
              <span>{{
                item.latency === null
                  ? "-"
                  : `${Math.round(item.latency).toLocaleString()} ms`
              }}</span
              ><span>{{
                item.cost === null ? "-" : `$${item.cost.toFixed(4)}`
              }}</span>
            </div>
            <p class="mt-3 text-xs font-medium text-blue-400">
              모델별 상세 보기 →
            </p>
          </button>
        </section>

        <section
          class="rounded-xl border border-slate-800 bg-slate-900/60 p-4 md:p-5"
        >
          <div class="mb-5 flex items-center justify-between gap-2">
            <div class="flex items-center gap-2">
              <BarChart3 class="h-5 w-5 text-blue-400" />
              <div>
                <h2 class="font-semibold">전체 지표 차트</h2>
                <p class="text-xs text-slate-500">
                  아래 지표를 여러 개 선택해 고정된 영역에서 동시에 비교하세요.
                </p>
              </div>
            </div>
            <output class="text-xs text-slate-400" aria-live="polite"
              >{{ selectedMetrics.length }}개 지표</output
            >
          </div>
          <div
            class="mb-6 flex flex-wrap gap-2"
            role="group"
            aria-label="비교 지표"
          >
            <button
              v-for="metric in metrics"
              :key="metric.key"
              type="button"
              :aria-pressed="selectedMetricKeys.includes(metric.key)"
              class="shrink-0 rounded-full border px-3 py-1.5 text-sm transition"
              :class="
                selectedMetricKeys.includes(metric.key)
                  ? 'border-blue-500 bg-blue-500/15 text-blue-300'
                  : 'border-slate-700 text-slate-400 hover:border-slate-500 disabled:cursor-not-allowed disabled:opacity-35'
              "
              @click="toggleMetric(metric.key)"
            >
              <span
                class="mr-1.5 inline-flex h-4 w-4 items-center justify-center rounded border align-text-bottom"
                :class="
                  selectedMetricKeys.includes(metric.key)
                    ? 'border-blue-400 bg-blue-500'
                    : 'border-slate-600'
                "
              >
                <Check
                  v-if="selectedMetricKeys.includes(metric.key)"
                  class="h-3 w-3"
                /> </span
              >{{ metric.label }}
            </button>
          </div>
          <div
            class="grid h-[520px] gap-3 overflow-y-auto pr-1"
            :style="chartGridStyle"
          >
            <article
              v-for="metric in selectedMetrics"
              :key="metric.key"
              class="min-h-0 rounded-xl border border-slate-800 bg-slate-950/40 p-3"
            >
              <div class="mb-2 flex items-center justify-between gap-2">
                <h3 class="truncate text-sm font-medium">{{ metric.label }}</h3>
                <span class="shrink-0 text-[10px] text-slate-500">{{
                  metric.better
                }}</span>
              </div>
              <div class="flex justify-between text-[9px] text-slate-600">
                <span>{{
                  formatAxis(metricDomain(metric.key).min, metric)
                }}</span
                ><span>선택 실험 범위 자동 확대</span
                ><span>{{
                  formatAxis(metricDomain(metric.key).max, metric)
                }}</span>
              </div>
              <div
                class="flex h-[calc(100%-2rem)] items-end justify-around gap-1 border-b border-slate-700 px-1"
                role="img"
                :aria-label="`${metric.label}: ${summaries.map((item) => `${item.run.name} ${metric.format(metricValue(item, metric.key))}`).join(', ')}`"
              >
                <div
                  v-for="item in summaries"
                  :key="item.run.id"
                  class="group relative flex h-full min-w-0 flex-1 flex-col justify-end text-center"
                >
                  <span class="mb-1 truncate text-[10px] font-semibold">{{
                    metric.format(metricValue(item, metric.key))
                  }}</span>
                  <div
                    class="mx-auto w-full max-w-12 rounded-t-md transition-all"
                    :style="{
                      height: chartHeight(
                        metricValue(item, metric.key),
                        metric.key,
                      ),
                      backgroundColor: item.color,
                    }"
                  />
                  <div
                    class="pointer-events-none absolute bottom-8 left-1/2 z-30 hidden w-max max-w-64 -translate-x-1/2 rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-left text-xs shadow-xl group-hover:block"
                  >
                    <p class="font-semibold text-white">{{ item.run.name }}</p>
                    <p class="mt-1 text-slate-300">
                      {{ metric.label }}:
                      <strong>{{
                        metric.format(metricValue(item, metric.key))
                      }}</strong>
                    </p>
                  </div>
                  <span
                    class="mt-2 truncate text-[10px] text-slate-400"
                    :title="item.run.name"
                    >#{{ item.order }}</span
                  >
                </div>
              </div>
            </article>
          </div>
        </section>

        <section
          class="overflow-hidden rounded-xl border border-slate-800 bg-slate-900/60"
        >
          <div class="flex items-center gap-2 border-b border-slate-800 p-4">
            <FlaskConical class="h-5 w-5 text-emerald-400" />
            <h2 class="font-semibold">실험 조건</h2>
          </div>
          <div class="overflow-x-auto">
            <table class="w-full min-w-[760px] text-sm">
              <caption class="sr-only">
                선택한 실험의 조건과 사용량 비교
              </caption>
              <thead class="bg-slate-950/60 text-left text-xs text-slate-500">
                <tr>
                  <th scope="col" class="p-3">
                    <button type="button" @click="sortBy('experiment')">
                      실험 {{ sortMark("experiment") }}
                    </button>
                  </th>
                  <th scope="col" class="p-3">유형</th>
                  <th scope="col" class="p-3">Easy:Hard</th>
                  <th scope="col" class="p-3">동시 요청</th>
                  <th scope="col" class="p-3">버전</th>
                  <th scope="col" class="p-3">데이터셋</th>
                  <th scope="col" class="p-3 text-right">토큰 / 비용</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="item in summaries"
                  :key="item.run.id"
                  class="border-t border-slate-800"
                >
                  <td class="p-3 font-medium">
                    <span
                      class="mr-2 inline-block h-2 w-2 rounded-full"
                      :style="{ backgroundColor: item.color }"
                    />{{ item.run.name }}
                  </td>
                  <td class="p-3">{{ item.mode }}</td>
                  <td class="p-3">{{ item.ratio }}</td>
                  <td class="p-3">{{ item.concurrency }}</td>
                  <td class="p-3">{{ item.version }}</td>
                  <td class="p-3 text-slate-400">
                    {{ item.run.dataset_name }}
                  </td>
                  <td class="p-3 text-right">
                    {{ item.tokens.toLocaleString() }} /
                    {{ item.cost === null ? "-" : `$${item.cost.toFixed(4)}` }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <details
          open
          class="overflow-hidden rounded-xl border border-slate-800 bg-slate-900/60"
        >
          <summary
            class="cursor-pointer border-b border-slate-800 p-4 font-semibold hover:bg-slate-800/40"
          >
            모델별 상세 결과
            <span class="ml-2 text-xs font-normal text-slate-500">
              선택한 실험 내부의 후보 세부 지표
            </span>
          </summary>
          <div class="overflow-x-auto">
            <table class="w-full min-w-[2800px] text-sm">
              <caption class="sr-only">
                선택한 실험의 모델별 상세 결과
              </caption>
              <thead class="bg-slate-950/60 text-left text-xs text-slate-500">
                <tr>
                  <th scope="col" class="p-3">실험</th>
                  <th scope="col" class="p-3">
                    <button type="button" @click="sortBy('candidate')">
                      모델 / 후보 {{ sortMark("candidate") }}
                    </button>
                  </th>
                  <th scope="col" class="p-3">유형</th>
                  <th scope="col" class="p-3 text-right">
                    <button type="button" @click="sortBy('accuracy')">
                      정확도 {{ sortMark("accuracy") }}
                    </button>
                  </th>
                  <th scope="col" class="p-3 text-right">Strict</th>
                  <th scope="col" class="p-3 text-right">Parse 실패</th>
                  <th scope="col" class="p-3 text-right">지연 p50</th>
                  <th scope="col" class="p-3 text-right">
                    <button type="button" @click="sortBy('latency')">
                      p95 지연 {{ sortMark("latency") }}
                    </button>
                  </th>
                  <th scope="col" class="p-3 text-right">
                    <button type="button" @click="sortBy('failure')">
                      실패율 {{ sortMark("failure") }}
                    </button>
                  </th>
                  <th scope="col" class="p-3 text-right">TTFT p50</th>
                  <th scope="col" class="p-3 text-right">TTFT p95</th>
                  <th scope="col" class="p-3 text-right">TPOT p50</th>
                  <th scope="col" class="p-3 text-right">TPOT p95</th>
                  <th scope="col" class="p-3 text-right">Throughput p50</th>
                  <th scope="col" class="p-3 text-right">Throughput p95</th>
                  <th scope="col" class="p-3 text-right">System TPS</th>
                  <th scope="col" class="p-3 text-right">Router p50</th>
                  <th scope="col" class="p-3 text-right">Router p95</th>
                  <th scope="col" class="p-3 text-right">KV min</th>
                  <th scope="col" class="p-3 text-right">KV avg</th>
                  <th scope="col" class="p-3 text-right">KV max</th>
                  <th scope="col" class="p-3 text-right">입력 토큰</th>
                  <th scope="col" class="p-3 text-right">출력 토큰</th>
                  <th scope="col" class="p-3 text-right">
                    <button type="button" @click="sortBy('tokens')">
                      토큰 {{ sortMark("tokens") }}
                    </button>
                  </th>
                  <th scope="col" class="p-3 text-right">
                    <button type="button" @click="sortBy('cost')">
                      비용 {{ sortMark("cost") }}
                    </button>
                  </th>
                  <th scope="col" class="p-3 text-right">문항/로그</th>
                  <th scope="col" class="p-3">Routing 분포</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="entry in sortedDetailRows"
                  :key="entry.row.id"
                  class="border-t border-slate-800 hover:bg-slate-800/30"
                >
                  <td class="max-w-[200px] truncate p-3 text-slate-400">
                    <span
                      class="mr-2 inline-block h-2 w-2 rounded-full"
                      :style="{ backgroundColor: entry.item.color }"
                    />{{ entry.item.run.name }}
                  </td>
                  <td class="p-3 font-medium">
                    {{
                      entry.row.candidate_label ||
                      entry.row.model_display_name ||
                      entry.row.model_name ||
                      "-"
                    }}
                  </td>
                  <td class="p-3">
                    {{
                      entry.row.result_type === "routing" ? "Routing" : "Single"
                    }}
                  </td>
                  <td class="p-3 text-right">
                    {{ percent(number(entry.row.overall_accuracy)) }}
                  </td>
                  <td class="p-3 text-right">
                    {{ percent(number(entry.row.strict_compliance_rate)) }}
                  </td>
                  <td class="p-3 text-right">
                    {{ percent(number(entry.row.parse_failure_rate)) }}
                  </td>
                  <td class="p-3 text-right">
                    {{ formatMs(number(entry.row.latency_p50_ms)) }}
                  </td>
                  <td class="p-3 text-right">
                    {{
                      number(entry.row.latency_p95_ms) === null
                        ? "-"
                        : `${number(entry.row.latency_p95_ms)?.toLocaleString()} ms`
                    }}
                  </td>
                  <td class="p-3 text-right">
                    {{ percent(number(entry.row.failure_rate)) }}
                  </td>
                  <td class="p-3 text-right">
                    {{ formatMs(number(entry.row.ttft_p50_ms)) }}
                  </td>
                  <td class="p-3 text-right">
                    {{ formatMs(number(entry.row.ttft_p95_ms)) }}
                  </td>
                  <td class="p-3 text-right">
                    {{ formatMs(number(entry.row.tpot_p50_ms)) }}
                  </td>
                  <td class="p-3 text-right">
                    {{ formatMs(number(entry.row.tpot_p95_ms)) }}
                  </td>
                  <td class="p-3 text-right">
                    {{
                      number(entry.row.throughput_p50_tps)?.toFixed(1) ?? "-"
                    }}
                  </td>
                  <td class="p-3 text-right">
                    {{
                      number(entry.row.throughput_p95_tps)?.toFixed(1) ?? "-"
                    }}
                  </td>
                  <td class="p-3 text-right">
                    {{
                      number(entry.row.system_throughput_tps)?.toFixed(1) ?? "-"
                    }}
                  </td>
                  <td class="p-3 text-right">
                    {{ formatMs(number(entry.row.router_latency_p50_ms)) }}
                  </td>
                  <td class="p-3 text-right">
                    {{ formatMs(number(entry.row.router_latency_p95_ms)) }}
                  </td>
                  <td class="p-3 text-right">
                    {{ percent(number(entry.row.kv_cache_usage_min)) }}
                  </td>
                  <td class="p-3 text-right">
                    {{ percent(number(entry.row.kv_cache_usage_avg)) }}
                  </td>
                  <td class="p-3 text-right">
                    {{ percent(number(entry.row.kv_cache_usage_max)) }}
                  </td>
                  <td class="p-3 text-right">
                    {{ entry.row.input_tokens.toLocaleString() }}
                  </td>
                  <td class="p-3 text-right">
                    {{ entry.row.output_tokens.toLocaleString() }}
                  </td>
                  <td class="p-3 text-right">
                    {{
                      (
                        (entry.row.input_tokens || 0) +
                        (entry.row.output_tokens || 0)
                      ).toLocaleString()
                    }}
                  </td>
                  <td class="p-3 text-right">
                    {{
                      number(entry.row.estimated_cost_usd) === null
                        ? "-"
                        : `$${number(entry.row.estimated_cost_usd)?.toFixed(5)}`
                    }}
                  </td>
                  <td class="p-3 text-right">
                    {{ entry.row.item_result_count.toLocaleString() }}
                  </td>
                  <td class="p-3">
                    {{
                      entry.row.result_type === "routing"
                        ? `Small ${entry.row.routing_model_distribution?.small?.percent ?? "-"}% / Large ${entry.row.routing_model_distribution?.large?.percent ?? "-"}%`
                        : "-"
                    }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </details>
      </div>
      <div
        v-else
        class="flex min-h-72 flex-col items-center justify-center rounded-xl border border-dashed border-slate-700 text-center"
      >
        <FlaskConical class="mb-3 h-9 w-9 text-slate-600" />
        <p class="font-medium">비교할 실험을 선택하세요</p>
        <p class="mt-1 text-sm text-slate-500">
          왼쪽 목록에서 실험을 선택하세요.
        </p>
      </div>
    </section>

    <div
      v-if="detailSummary"
      class="fixed inset-0 z-50 bg-black/80 p-3 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      :aria-label="`${detailSummary.run.name} 실험 상세`"
      @click.self="detailRunId = null"
    >
      <section
        class="mx-auto flex h-full w-full max-w-[1700px] flex-col overflow-hidden rounded-2xl border border-slate-700 bg-slate-950 shadow-2xl"
      >
        <header
          class="flex shrink-0 items-start justify-between gap-4 border-b border-slate-800 px-5 py-3"
        >
          <div class="min-w-0 flex-1">
            <p class="text-xs font-medium text-blue-400">
              MODEL COMPARISON DETAIL
            </p>
            <h2 class="truncate font-bold">{{ detailSummary.run.name }}</h2>
            <div class="mt-2 flex flex-wrap gap-1.5 text-[11px]">
              <span class="rounded bg-blue-500/15 px-2 py-1 text-blue-300">{{
                detailSummary.mode
              }}</span>
              <span class="rounded bg-slate-800 px-2 py-1"
                >E:H {{ detailSummary.ratio }}</span
              >
              <span class="rounded bg-slate-800 px-2 py-1"
                >동시성 {{ detailSummary.concurrency }}</span
              >
              <span class="rounded bg-slate-800 px-2 py-1">{{
                detailSummary.version
              }}</span>
              <span class="rounded bg-slate-800 px-2 py-1"
                >{{ detailSummary.run.dataset_name }} ·
                {{
                  detailSummary.run.dataset_question_count.toLocaleString()
                }}문항</span
              >
              <span class="rounded bg-slate-800 px-2 py-1">{{
                detailSummary.run.evaluation_method_name ?? "평가방식 미지정"
              }}</span>
              <span class="rounded bg-slate-800 px-2 py-1"
                >후보 {{ detailSummary.rows.length }} · 표본
                {{ detailSummary.sampleCount.toLocaleString() }}</span
              >
              <span class="rounded bg-emerald-500/15 px-2 py-1 text-emerald-300"
                >정확도 {{ percent(detailSummary.accuracy) }}</span
              >
              <span class="rounded bg-amber-500/15 px-2 py-1 text-amber-300"
                >p95 {{ formatMs(detailSummary.latency) }}</span
              >
              <span class="rounded bg-slate-800 px-2 py-1"
                >상태 {{ detailSummary.run.status }} ·
                {{ formatDate(detailSummary.run.completed_at) }}</span
              >
            </div>
          </div>
          <button
            type="button"
            class="rounded-lg border border-slate-700 px-3 py-2 text-sm hover:bg-slate-800"
            aria-label="실험 상세 닫기"
            @click="detailRunId = null"
          >
            닫기 ×
          </button>
        </header>
        <div class="compact-detail min-h-0 flex-1 overflow-y-auto">
          <ExperimentModelDetail :key="detailSummary.run.id" />
        </div>
      </section>
    </div>
  </main>
</template>

<style scoped>
.compact-detail :deep(.page-shell) {
  max-width: none;
  padding: 0.75rem;
}
.compact-detail :deep(.page-header) {
  display: none;
}
.compact-detail :deep(.section-card) {
  padding: 0.75rem !important;
}
.compact-detail :deep(.section-card-padded) {
  padding: 0.75rem !important;
}
.compact-detail :deep(.grid) {
  gap: 0.6rem !important;
}
.compact-detail :deep([class~="h-56"]) {
  height: 8.5rem !important;
}
.compact-detail :deep([class~="h-24"]) {
  height: 4.5rem !important;
}
.compact-detail :deep([class~="w-24"]) {
  width: 4.5rem !important;
}
.compact-detail :deep([class~="min-h-72"]) {
  min-height: 10rem !important;
}
.compact-detail :deep(svg[viewBox="0 0 780 310"]) {
  max-height: 12rem;
}
.compact-detail :deep(.mb-6) {
  margin-bottom: 0.75rem !important;
}
.compact-detail :deep(.mt-6) {
  margin-top: 0.75rem !important;
}
@media (min-width: 1200px) {
  .compact-detail :deep([class~="xl:grid-cols-2"]) {
    grid-template-columns: repeat(4, minmax(0, 1fr)) !important;
  }
}
.compact-detail :deep(table th),
.compact-detail :deep(table td) {
  padding: 0.5rem !important;
}
.compact-detail :deep(h2),
.compact-detail :deep(h3) {
  line-height: 1.2;
}
</style>
