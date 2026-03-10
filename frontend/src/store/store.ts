import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';

interface User {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  role: string;
  avatar?: string;
}

interface Notification {
  id: number;
  title: string;
  message: string;
  type: 'info' | 'success' | 'warning' | 'error';
  is_read: boolean;
  created_at: string;
}

interface AppState {
  user: User | null;
  isAuthenticated: boolean;
  notifications: Notification[];
  unreadCount: number;
  sidebarCollapsed: boolean;
  theme: 'light' | 'dark';
  isLoading: boolean;

  setUser: (user: User | null) => void;
  setAuthenticated: (value: boolean) => void;
  setNotifications: (notifications: Notification[]) => void;
  addNotification: (notification: Notification) => void;
  markNotificationRead: (id: number) => void;
  markAllNotificationsRead: () => void;
  toggleSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  setTheme: (theme: 'light' | 'dark') => void;
  toggleTheme: () => void;
  setLoading: (loading: boolean) => void;
  reset: () => void;
}

const initialState = {
  user: null,
  isAuthenticated: false,
  notifications: [],
  unreadCount: 0,
  sidebarCollapsed: false,
  theme: 'light' as const,
  isLoading: false,
};

export const useAppStore = create<AppState>()(
  devtools(
    persist(
      (set, get) => ({
        ...initialState,

        setUser: (user) => set({ user, isAuthenticated: !!user }),
        setAuthenticated: (value) => set({ isAuthenticated: value }),

        setNotifications: (notifications) => set({
          notifications,
          unreadCount: notifications.filter(n => !n.is_read).length,
        }),

        addNotification: (notification) => {
          const current = get().notifications;
          set({
            notifications: [notification, ...current],
            unreadCount: get().unreadCount + (notification.is_read ? 0 : 1),
          });
        },

        markNotificationRead: (id) => {
          const notifications = get().notifications.map(n =>
            n.id === id ? { ...n, is_read: true } : n
          );
          set({
            notifications,
            unreadCount: notifications.filter(n => !n.is_read).length,
          });
        },

        markAllNotificationsRead: () => {
          const notifications = get().notifications.map(n => ({ ...n, is_read: true }));
          set({ notifications, unreadCount: 0 });
        },

        toggleSidebar: () => set({ sidebarCollapsed: !get().sidebarCollapsed }),
        setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),

        setTheme: (theme) => {
          document.documentElement.classList.toggle('dark', theme === 'dark');
          set({ theme });
        },

        toggleTheme: () => {
          const newTheme = get().theme === 'light' ? 'dark' : 'light';
          document.documentElement.classList.toggle('dark', newTheme === 'dark');
          set({ theme: newTheme });
        },

        setLoading: (loading) => set({ isLoading: loading }),

        reset: () => {
          localStorage.removeItem('auth_tokens');
          set(initialState);
        },
      }),
      {
        name: 'app-storage',
        partialize: (state) => ({
          theme: state.theme,
          sidebarCollapsed: state.sidebarCollapsed,
        }),
      }
    )
  )
);

export default useAppStore;
