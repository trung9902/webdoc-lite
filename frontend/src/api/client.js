import axios from 'axios';

export const API_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8098').replace(/\/$/, '');

const ACCESS = 'accessToken';
const REFRESH = 'refreshToken';

export const tokens = {
  get: () => localStorage.getItem(ACCESS),
  set: (access, refresh) => {
    localStorage.setItem(ACCESS, access);
    if (refresh) localStorage.setItem(REFRESH, refresh);
  },
  clear: () => {
    localStorage.removeItem(ACCESS);
    localStorage.removeItem(REFRESH);
  },
};

const api = axios.create({ baseURL: `${API_URL}/api/v1` });

api.interceptors.request.use((config) => {
  const token = tokens.get();

  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

let refreshing = null;

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config;
    const isAuthCall = original?.url?.includes('/auth/');

    if (error.response?.status === 401 && !original._retried && !isAuthCall) {
      original._retried = true;
      const refreshToken = localStorage.getItem(REFRESH);

      if (refreshToken) {
        try {
          refreshing =
            refreshing ||
            axios
              .post(`${API_URL}/api/v1/auth/refresh-token`, { refresh_token: refreshToken })
              .finally(() => {
                refreshing = null;
              });
          const { data } = await refreshing;

          tokens.set(data.access_token, data.refresh_token);
          original.headers.Authorization = `Bearer ${data.access_token}`;
          return api(original);
        } catch {
          // hết hạn hẳn: rơi xuống phần đăng xuất bên dưới
        }
      }
      tokens.clear();
      window.dispatchEvent(new Event('auth:logout'));
    }
    return Promise.reject(error);
  },
);

/** Lấy thông báo lỗi tiếng Việt từ phản hồi của backend. */
export const errorMessage = (error) =>
  error?.response?.data?.message || 'Không kết nối được máy chủ. Hãy kiểm tra backend đã chạy chưa.';

export default api;
