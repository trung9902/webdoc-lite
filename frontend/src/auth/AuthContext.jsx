import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import api, { tokens } from '../api/client';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [me, setMe] = useState(null);
  const [loading, setLoading] = useState(Boolean(tokens.get()));

  const reload = useCallback(async () => {
    try {
      const { data } = await api.get('/users/profile');

      setMe(data);
      return data;
    } catch {
      setMe(null);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (tokens.get()) reload();
    const onLogout = () => setMe(null);

    window.addEventListener('auth:logout', onLogout);
    return () => window.removeEventListener('auth:logout', onLogout);
  }, [reload]);

  const login = async (username, password) => {
    const { data } = await api.post('/auth/login', { email: username, password });

    tokens.set(data.access_token, data.refresh_token);
    return reload();
  };

  const logout = () => {
    tokens.clear();
    setMe(null);
  };

  const value = useMemo(
    () => ({
      me,
      loading,
      login,
      logout,
      reload,
      /** Có quyền (permission) này không, ví dụ can('gaa.search'). */
      can: (permission) => Boolean(me?.permissionNames?.includes(permission)),
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [me, loading],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => useContext(AuthContext);
