import { ConfigProvider, Spin } from 'antd';
import viVN from 'antd/locale/vi_VN';
import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom';

import { AuthProvider, useAuth } from './auth/AuthContext';
import AppLayout from './layout/AppLayout';
import LoginPage from './pages/LoginPage';
import { spacing } from './theme/colors';
import { ThemeProvider, useTheme } from './theme/ThemeContext';

import './theme/global.css';

/** Chưa đăng nhập thì chuyển về /login và nhớ trang đang muốn vào. */
const RequireAuth = ({ children }) => {
  const { me, loading } = useAuth();
  const location = useLocation();

  if (loading) return <Spin style={{ display: 'block', marginTop: 120 }} />;
  if (!me) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  return children;
};

/** Cấu hình Ant Design theo giao diện đang chọn: phông, màu chính, bo góc, cỡ control. */
const Themed = ({ children }) => {
  const { colors } = useTheme();

  return (
    <ConfigProvider
      locale={viVN}
      componentSize="large"
      theme={{
        token: { fontFamily: "'Be Vietnam Pro', 'Noto Sans', sans-serif", colorPrimary: colors.buttonPrimary, borderRadius: spacing.borderRadius.xl },
        components: { Layout: { headerBg: '#FFFFFF' }, Divider: { margin: 16, marginLG: 16 } },
      }}
    >
      {children}
    </ConfigProvider>
  );
};

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ThemeProvider>
      <Themed>
        <BrowserRouter>
          <AuthProvider>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route
                path="/*"
                element={
                  <RequireAuth>
                    <AppLayout />
                  </RequireAuth>
                }
              />
            </Routes>
          </AuthProvider>
        </BrowserRouter>
      </Themed>
    </ThemeProvider>
  </React.StrictMode>,
);
