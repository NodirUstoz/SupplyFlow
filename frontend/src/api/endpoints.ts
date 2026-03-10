import apiClient from './client';

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface ApiParams {
  page?: number;
  page_size?: number;
  search?: string;
  ordering?: string;
  [key: string]: any;
}

export const authAPI = {
  login: (email: string, password: string) =>
    apiClient.post('/auth/login/', { email, password }),
  register: (data: { email: string; password: string; first_name: string; last_name: string }) =>
    apiClient.post('/auth/register/', data),
  logout: (refresh: string) =>
    apiClient.post('/auth/logout/', { refresh }),
  getProfile: () =>
    apiClient.get('/auth/me/'),
  updateProfile: (data: Record<string, any>) =>
    apiClient.patch('/auth/me/', data),
  changePassword: (data: { old_password: string; new_password: string }) =>
    apiClient.post('/auth/change-password/', data),
  forgotPassword: (email: string) =>
    apiClient.post('/auth/forgot-password/', { email }),
  resetPassword: (data: { token: string; password: string }) =>
    apiClient.post('/auth/reset-password/', data),
  refreshToken: (refresh: string) =>
    apiClient.post('/auth/token/refresh/', { refresh }),
};

export const createCrudAPI = <T>(basePath: string) => ({
  getAll: (params?: ApiParams) =>
    apiClient.get<PaginatedResponse<T>>(basePath, { params }),
  getById: (id: number | string) =>
    apiClient.get<T>(`${basePath}${id}/`),
  create: (data: Partial<T>) =>
    apiClient.post<T>(basePath, data),
  update: (id: number | string, data: Partial<T>) =>
    apiClient.put<T>(`${basePath}${id}/`, data),
  partialUpdate: (id: number | string, data: Partial<T>) =>
    apiClient.patch<T>(`${basePath}${id}/`, data),
  delete: (id: number | string) =>
    apiClient.delete(`${basePath}${id}/`),
});

export const dashboardAPI = {
  getStats: () => apiClient.get('/dashboard/stats/'),
  getRecentActivity: () => apiClient.get('/dashboard/activity/'),
  getChartData: (params?: { period?: string }) => apiClient.get('/dashboard/charts/', { params }),
};

export const notificationsAPI = {
  getAll: (params?: ApiParams) => apiClient.get('/notifications/', { params }),
  markAsRead: (id: number) => apiClient.patch(`/notifications/${id}/`, { is_read: true }),
  markAllRead: () => apiClient.post('/notifications/mark-all-read/'),
  getUnreadCount: () => apiClient.get('/notifications/unread-count/'),
};

export const uploadAPI = {
  uploadFile: (file: File, path?: string) => {
    const formData = new FormData();
    formData.append('file', file);
    if (path) formData.append('path', path);
    return apiClient.post('/uploads/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  deleteFile: (id: number) => apiClient.delete(`/uploads/${id}/`),
};
