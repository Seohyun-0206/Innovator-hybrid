<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import Dashboard from './pages/Dashboard.vue'
import Models from './pages/Models.vue'
import Policies from './pages/Policies.vue'
import ThresholdRules from './pages/ThresholdRules.vue'
import ProviderCredentials from './pages/ProviderCredentials.vue'
import Playground from './pages/Playground.vue'
import RoutingLogs from './pages/RoutingLogs.vue'
import Users from './pages/Users.vue'
import ModelEvaluation from './pages/ModelEvaluation.vue'
import EvaluationDatasets from './pages/EvaluationDatasets.vue'
import GeneratedDatasets from './pages/GeneratedDatasets.vue'
import EvaluationMethods from './pages/EvaluationMethods.vue'
import EvaluationRuns from './pages/EvaluationRuns.vue'
import EvaluationItemResults from './pages/EvaluationItemResults.vue'
import EvaluationArtifacts from './pages/EvaluationArtifacts.vue'
import ServiceFeatureMapping from './pages/ServiceFeatureMapping.vue'
import Login from './pages/Login.vue'
import {
  ArchiveIcon,
  BotIcon,
  ClipboardListIcon,
  CpuIcon,
  DatabaseIcon,
  FileSearchIcon,
  KeyRoundIcon,
  FlaskConicalIcon,
  LayersIcon,
  LayoutDashboardIcon,
  LogOutIcon,
  MoonIcon,
  PlayIcon,
  RouteIcon,
  SlidersHorizontalIcon,
  SunIcon,
  UsersIcon,
  XIcon
} from 'lucide-vue-next'
import { AppUser, LoginResponse, clearAuthToken, getAuthToken, setAuthToken, useApi } from './composables/useApi'
import { useTheme } from './composables/useTheme'

const tabs = [
  { id: 'dashboard', label: '대시보드', component: Dashboard, group: 'dashboard', icon: LayoutDashboardIcon },
  { id: 'evaluation-runs', label: '실험 실행', component: EvaluationRuns, group: 'experiments', icon: PlayIcon },
  { id: 'model-evaluation', label: '결과 분석', component: ModelEvaluation, group: 'experiments', icon: FlaskConicalIcon },
  { id: 'evaluation-item-results', label: '문항별 로그', component: EvaluationItemResults, group: 'experiments', icon: FileSearchIcon },
  { id: 'evaluation-artifacts', label: '산출물', component: EvaluationArtifacts, group: 'experiments', icon: ArchiveIcon },
  { id: 'models', label: '모델', component: Models, group: 'resources', icon: CpuIcon },
  { id: 'evaluation-datasets', label: '데이터셋', component: EvaluationDatasets, group: 'resources', icon: DatabaseIcon },
  { id: 'generated-datasets', label: '생성 데이터셋', component: GeneratedDatasets, group: 'resources', icon: DatabaseIcon },
  { id: 'evaluation-methods', label: '평가방식', component: EvaluationMethods, group: 'resources', icon: ClipboardListIcon },
  { id: 'service-features', label: '정책 설계', component: ServiceFeatureMapping, group: 'policy-design', icon: LayersIcon },
  { id: 'playground', label: '테스트', component: Playground, group: 'policy-design', icon: BotIcon },
  { id: 'policies', label: '라우팅 정책', component: Policies, group: 'policy-design', icon: RouteIcon },
  { id: 'threshold-rules', label: 'SLA/검증 기준', component: ThresholdRules, group: 'policy-design', icon: SlidersHorizontalIcon },
  { id: 'logs', label: '라우팅 로그', component: RoutingLogs, group: 'policy-design', icon: FileSearchIcon },
  { id: 'users', label: '사용자/권한', component: Users, group: 'admin', icon: UsersIcon },
  { id: 'credentials', label: '인증/보안', component: ProviderCredentials, group: 'admin', icon: KeyRoundIcon }
] as const

type TabId = (typeof tabs)[number]['id']

const navGroups = [
  { id: 'dashboard', label: '대시보드' },
  { id: 'experiments', label: '실험' },
  { id: 'resources', label: '리소스' },
  { id: 'policy-design', label: '정책 설계' },
  { id: 'admin', label: '관리' }
] as const

const { isDark, toggle: toggleTheme } = useTheme()
const api = useApi()
const currentUser = ref<AppUser | null>(null)
const authReady = ref(false)
const activeTab = ref<TabId>('dashboard')
const openTabs = ref<TabId[]>(['dashboard'])
const visibleTabs = computed(() =>
  tabs.filter((tab) => currentUser.value?.allowed_screens.includes(tab.id) ?? false)
)
const visibleNavGroups = computed(() =>
  navGroups
    .map((group) => ({
      ...group,
      tabs: visibleTabs.value.filter((tab) => tab.group === group.id)
    }))
    .filter((group) => group.tabs.length > 0)
)
const openTabItems = computed(() =>
  openTabs.value
    .map((tabId) => visibleTabs.value.find((tab) => tab.id === tabId))
    .filter((tab): tab is (typeof tabs)[number] => Boolean(tab))
)

function syncOpenTabsWithAccess() {
  const allowedIds = visibleTabs.value.map((tab) => tab.id)
  openTabs.value = openTabs.value.filter((tabId) => allowedIds.includes(tabId))

  if (!openTabs.value.length && visibleTabs.value[0]) {
    openTabs.value = [visibleTabs.value[0].id]
  }

  if (!openTabs.value.includes(activeTab.value) && openTabs.value[0]) {
    activeTab.value = openTabs.value[0]
  }
}

function openWorkspaceTab(tabId: TabId) {
  if (!visibleTabs.value.some((tab) => tab.id === tabId)) {
    return
  }
  if (!openTabs.value.includes(tabId)) {
    openTabs.value.push(tabId)
  }
  activeTab.value = tabId
}

function closeWorkspaceTab(tabId: TabId) {
  if (openTabs.value.length <= 1) {
    return
  }

  const closingIndex = openTabs.value.indexOf(tabId)
  openTabs.value = openTabs.value.filter((id) => id !== tabId)

  if (activeTab.value === tabId) {
    const fallbackIndex = Math.max(0, closingIndex - 1)
    activeTab.value = openTabs.value[fallbackIndex] ?? openTabs.value[0]
  }
}

function closeAllWorkspaceTabs() {
  const fallbackTab = visibleTabs.value.find((tab) => tab.id === 'dashboard') ?? visibleTabs.value[0]
  if (!fallbackTab) {
    openTabs.value = []
    return
  }
  openTabs.value = [fallbackTab.id]
  activeTab.value = fallbackTab.id
}

function handleOpenWorkspaceTab(event: Event) {
  const tabId = (event as CustomEvent<TabId>).detail
  if (tabId) {
    openWorkspaceTab(tabId)
  }
}

async function loadMe() {
  try {
    currentUser.value = await api.getMe()
    syncOpenTabsWithAccess()
  } catch {
    clearAuthToken()
    currentUser.value = null
  } finally {
    authReady.value = true
  }
}

function handleLoggedIn(response: LoginResponse) {
  setAuthToken(response.token)
  currentUser.value = response.user
  syncOpenTabsWithAccess()
  authReady.value = true
}

async function logout() {
  try {
    await api.logout()
  } catch {
    // ignore server logout failure
  }
  clearAuthToken()
  currentUser.value = null
  activeTab.value = 'dashboard'
  openTabs.value = ['dashboard']
}

onMounted(async () => {
  window.addEventListener('open-workspace-tab', handleOpenWorkspaceTab)
  if (getAuthToken()) {
    await loadMe()
  } else {
    authReady.value = true
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('open-workspace-tab', handleOpenWorkspaceTab)
})
</script>

<template>
  <Login v-if="authReady && !currentUser" @logged-in="handleLoggedIn" />

  <div v-else-if="authReady" class="min-h-screen bg-zinc-950">
    <!-- Sidebar -->
    <aside class="fixed inset-y-0 left-0 z-30 flex w-64 shrink-0 flex-col border-r border-zinc-800/60 bg-sidebar">
      <!-- Logo -->
      <div class="flex items-center gap-3 border-b border-zinc-800/60 px-5 py-5">
        <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600">
          <BotIcon class="h-4 w-4 text-white" />
        </div>
        <div>
          <p class="text-[10px] font-semibold uppercase tracking-widest text-zinc-500">AI Experiment</p>
          <p class="text-sm font-semibold text-zinc-100 leading-tight">Platform Admin</p>
        </div>
      </div>

      <!-- Navigation -->
      <nav class="flex-1 overflow-y-auto px-3 py-4 space-y-6">
        <div v-for="group in visibleNavGroups" :key="group.id">
          <p class="mb-1 px-2 text-[10px] font-semibold uppercase tracking-widest text-zinc-600">
            {{ group.label }}
          </p>
          <div class="space-y-0.5">
            <button
              v-for="tab in group.tabs"
              :key="tab.id"
              :class="[
                'flex w-full items-center gap-3 rounded-md py-2 pr-2.5 text-sm font-medium transition-all duration-150',
                activeTab === tab.id ? 'nav-item-active' : 'nav-item-hover'
              ]"
              @click="openWorkspaceTab(tab.id)"
            >
              <component
                :is="tab.icon"
                :class="['h-4 w-4 shrink-0', activeTab === tab.id ? 'text-indigo-400' : 'text-zinc-500']"
              />
              {{ tab.label }}
            </button>
          </div>
        </div>
      </nav>

      <!-- User footer -->
      <div class="border-t border-zinc-800/60 p-3">
        <div class="group flex items-center gap-3 rounded-lg p-2 transition-colors hover:bg-indigo-500/5">
          <div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-zinc-700">
            <span class="text-xs font-semibold uppercase text-zinc-300">
              {{ currentUser?.username?.charAt(0) ?? '?' }}
            </span>
          </div>
          <div class="min-w-0 flex-1">
            <p class="truncate text-sm font-medium text-zinc-200">{{ currentUser?.username }}</p>
            <p class="text-xs text-zinc-500">{{ currentUser?.is_staff ? 'Admin' : 'User' }}</p>
          </div>
          <button
            class="shrink-0 rounded p-1.5 text-zinc-500 transition-colors hover:bg-indigo-500/10 hover:text-indigo-200"
            :title="isDark ? 'Switch to Light mode' : 'Switch to Dark mode'"
            type="button"
            @click="toggleTheme"
          >
            <SunIcon v-if="isDark" class="h-4 w-4" />
            <MoonIcon v-else class="h-4 w-4" />
          </button>
          <button
            class="shrink-0 rounded p-1.5 text-zinc-500 transition-colors hover:bg-indigo-500/10 hover:text-indigo-200"
            title="Logout"
            type="button"
            @click="logout"
          >
            <LogOutIcon class="h-4 w-4" />
          </button>
        </div>
      </div>
    </aside>

    <!-- Main content -->
    <main class="ml-64 flex min-h-screen min-w-0 flex-col overflow-hidden">
      <div class="flex min-h-12 shrink-0 items-end border-b border-zinc-800/60 bg-zinc-950 px-3 pt-2">
        <div class="flex min-w-0 flex-1 items-end overflow-x-auto">
          <button
            v-for="tab in openTabItems"
            :key="tab.id"
            :class="[
              'group mr-1 flex h-10 min-w-36 max-w-56 items-center justify-between gap-3 rounded-t-lg border px-3 text-sm font-medium transition-colors',
              activeTab === tab.id ? 'tab-active' : 'tab-inactive'
            ]"
            type="button"
            @click="activeTab = tab.id"
          >
            <span class="truncate">{{ tab.label }}</span>
            <span
              :class="[
                'rounded p-0.5 transition-colors',
                openTabItems.length <= 1
                  ? 'cursor-default text-zinc-700'
                  : 'tab-close-hover'
              ]"
              role="button"
              tabindex="0"
              :title="openTabItems.length <= 1 ? '최소 하나의 탭은 유지됩니다' : '탭 닫기'"
              @click.stop="closeWorkspaceTab(tab.id)"
              @keydown.enter.stop.prevent="closeWorkspaceTab(tab.id)"
              @keydown.space.stop.prevent="closeWorkspaceTab(tab.id)"
            >
              <XIcon class="h-4 w-4" />
            </span>
          </button>
        </div>
        <button
          class="mb-1 ml-2 shrink-0 rounded-md border border-zinc-800 px-3 py-1.5 text-xs font-medium text-zinc-500 transition-colors hover:border-indigo-500/30 hover:bg-indigo-500/5 hover:text-indigo-200 disabled:cursor-not-allowed disabled:opacity-40"
          :disabled="openTabItems.length <= 1"
          title="열린 탭을 모두 닫고 기본 화면만 남깁니다"
          type="button"
          @click="closeAllWorkspaceTabs"
        >
          모두 닫기
        </button>
      </div>

      <div class="min-h-0 flex-1 overflow-auto">
        <component
          v-for="tab in openTabItems"
          :key="tab.id"
          :is="tab.component"
          v-show="activeTab === tab.id"
        />
      </div>
    </main>
  </div>

  <!-- Loading state -->
  <main v-else class="flex min-h-screen items-center justify-center bg-zinc-950">
    <div class="flex items-center gap-3 text-zinc-500">
      <div class="h-4 w-4 animate-spin rounded-full border-2 border-zinc-700 border-t-indigo-500"></div>
      <span class="text-sm">Loading...</span>
    </div>
  </main>
</template>
