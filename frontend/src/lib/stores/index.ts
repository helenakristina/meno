/**
 * Central export point for all stores
 * Import from $lib/stores instead of $lib/stores/[store]
 */

export { authState, isAuthenticated, type AuthState } from './auth';
export { appStore, isAppLoading, withLoading, type Notification, type AppState } from './app';
