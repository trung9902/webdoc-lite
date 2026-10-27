import { LockOutlined, UserOutlined } from '@ant-design/icons';
import { Alert, Button, Flex, Form, Grid, Image, Input, Typography } from 'antd';
import { useEffect, useState } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';

import { errorMessage } from '../api/client';
import searchPic from '../assets/search.png';
import { useAuth } from '../auth/AuthContext';
import Logo from '../components/Logo';
import palette, { spacing } from '../theme/colors';

const LoginPage = () => {
  const { me, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const screens = Grid.useBreakpoint();
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    document.title = 'Đăng nhập';
  }, []);

  if (me) return <Navigate to={location.state?.from || '/'} replace />;

  const onFinish = async ({ username, password }) => {
    setLoading(true);
    setError(null);
    try {
      await login(username, password);
      navigate(location.state?.from || '/', { replace: true });
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Flex
      justify="center"
      align="center"
      vertical={!screens.lg}
      gap={screens.lg ? 80 : 32}
      style={{ width: '100%', minHeight: '100vh', boxSizing: 'border-box', backgroundColor: palette.gray.white, padding: '36px 0' }}
    >
      {screens.md && (
        <Flex justify="center" align="center" vertical style={{ width: 481 }}>
          <Flex style={{ paddingRight: 32 }}>
            <Image width={520} src={searchPic} preview={false} />
          </Flex>
        </Flex>
      )}

      <Flex
        justify="center"
        align="center"
        vertical
        gap={16}
        style={{
          padding: screens.sm ? '112px 120px' : '48px 24px',
          borderRadius: spacing.borderRadius.xxl,
          backgroundColor: palette.gray[10],
          width: screens.sm ? 608 : '100%',
          maxWidth: '100%',
          boxShadow: palette.boxShadow,
        }}
      >
        <Logo size="medium" />
        <Typography.Title level={2} style={{ color: palette.blue[90], margin: 0 }}>
          Đăng nhập
        </Typography.Title>

        <Form name="loginForm" initialValues={{ remember: false }} onFinish={onFinish} onValuesChange={() => setError(null)} size="large" autoComplete="on" style={{ width: '100%' }}>
          {error && <Alert message={error} type="error" showIcon closable onClose={() => setError(null)} style={{ width: '100%', marginBottom: 16 }} />}
          <Form.Item name="username" rules={[{ required: true, message: 'Nhập tên đăng nhập' }]}>
            <Input placeholder="Tài khoản" prefix={<UserOutlined />} autoComplete="username" autoFocus />
          </Form.Item>
          <Form.Item name="password" rules={[{ required: true, message: 'Nhập mật khẩu' }]}>
            <Input.Password placeholder="Mật khẩu" prefix={<LockOutlined />} autoComplete="current-password" />
          </Form.Item>
          <Form.Item style={{ marginBottom: 0 }}>
            <Button htmlType="submit" type="primary" style={{ width: '100%' }} loading={loading}>
              Đăng nhập
            </Button>
          </Form.Item>
        </Form>
      </Flex>
    </Flex>
  );
};

export default LoginPage;
