const trimTrailingSlash = (value: string) => value.replace(/\/+$/, '')

export const appEnv = {
  apiBaseUrl: trimTrailingSlash(import.meta.env.VITE_API_BASE_URL || ''),
  apiProxyTarget: trimTrailingSlash(import.meta.env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8000')
}
