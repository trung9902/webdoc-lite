import { ControlOutlined, MenuOutlined, MoonOutlined, RollbackOutlined, SunOutlined, UserOutlined } from '@ant-design/icons';
import { SignOut, User } from '@phosphor-icons/react';
import { Badge, Button, Drawer, Dropdown, Flex, Grid, Layout, Menu, Result, Tooltip, Typography } from 'antd';
import { useMemo, useState } from 'react';
import { Link, Route, Routes, useLocation, useNavigate } from 'react-router-dom';

import { useAuth } from '../auth/AuthContext';
import Logo from '../components/Logo';
import ProfileModal from '../components/ProfileModal';
import { groups, pages } from '../menu';
import palette, { spacing } from '../theme/colors';
import { useTheme } from '../theme/ThemeContext';

const { Sider, Content } = Layout;

const THEME_LABELS = { light: 'Sáng', dark: 'Tối', olive: 'Xanh Olive', redlight: 'Đỏ nhạt' };
const THEME_DOT = { olive: '#135200', redlight: '#ff4d4f' };

/** Khoá menu của một trang: đường dẫn kèm query nếu có (ví dụ /organization?tab=users). */
const keyOf = (p) => p.to ?? p.path;

const AppLayout = () => {
  const { me, can, logout } = useAuth();
  const { colors, changeTheme } = useTheme();
  const navigate = useNavigate();
  const location = useLocation();
  const screens = Grid.useBreakpoint();
  const [collapsed, setCollapsed] = useState(false);
  const [drawer, setDrawer] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [userMenu, setUserMenu] = useState('main');
  const [userMenuOpen, setUserMenuOpen] = useState(false);

  const isMobile = screens.xs === true;
  const allowed = pages.filter((p) => p.visible(me, can));
  const lightLogo = colors.sidebarText === '#ffffff';

  // Mục đang chọn: khớp cả query (tab) trước, nếu không thì khớp đường dẫn dài nhất.
  const selectedKey = useMemo(() => {
    const full = `${location.pathname}${location.search}`;
    const exact = allowed.find((p) => keyOf(p) === full);

    if (exact) return keyOf(exact);
    const byPath = allowed
      .filter((p) => p.path === location.pathname || (p.path !== '/' && location.pathname.startsWith(`${p.path}/`)))
      .sort((a, b) => b.path.length - a.path.length)[0];

    return byPath ? keyOf(byPath) : '';
  }, [allowed, location.pathname, location.search]);

  const menuItems = useMemo(() => {
    const items = [];
    const groupItems = {};

    allowed.forEach((p) => {
      const leaf = { key: keyOf(p), label: p.label, icon: p.icon };

      if (!p.group) {
        items.push(leaf);
        return;
      }
      if (!groupItems[p.group]) {
        groupItems[p.group] = { key: `group:${p.group}`, icon: groups[p.group].icon, label: groups[p.group].label, children: [] };
        items.push(groupItems[p.group]);
      }
      groupItems[p.group].children.push(leaf);
    });
    return items;
  }, [allowed]);

  const openKeys = useMemo(() => {
    const current = allowed.find((p) => keyOf(p) === selectedKey);

    return current?.group ? [`group:${current.group}`] : [];
  }, [allowed, selectedKey]);

  const roleText = me.organizationManager ? 'Quản lý tổ chức' : me.deptManager ? 'Quản lý phòng ban' : 'Người dùng';

  const goto = ({ key }) => {
    if (key.startsWith('group:')) return;
    navigate(key);
    setDrawer(false);
  };

  const sideMenu = (
    <Menu
      mode="inline"
      theme={colors.themeSidebar}
      forceSubMenuRender
      defaultOpenKeys={openKeys}
      selectedKeys={[selectedKey]}
      items={menuItems}
      onClick={goto}
      style={{ borderRight: 0, background: colors.sidebar, color: colors.sidebarText, flex: 1 }}
    />
  );

  const userItems =
    userMenu === 'main'
      ? [
          { key: 'profile', label: 'Thông tin tài khoản', icon: <UserOutlined /> },
          { key: 'goTo-theme', label: 'Thay đổi giao diện', icon: <ControlOutlined /> },
          { key: 'logout', label: 'Đăng xuất', icon: <SignOut size={16} /> },
        ]
      : [
          { key: 'backTo-main', label: 'Quay lại', icon: <RollbackOutlined /> },
          { key: 'theme-light', label: THEME_LABELS.light, icon: <SunOutlined /> },
          { key: 'theme-dark', label: THEME_LABELS.dark, icon: <MoonOutlined /> },
          ...['olive', 'redlight'].map((t) => ({
            key: `theme-${t}`,
            label: THEME_LABELS[t],
            icon: <span style={{ display: 'inline-block', width: 14, height: 14, borderRadius: '50%', background: THEME_DOT[t] }} />,
          })),
        ];

  const onUserMenu = ({ key }) => {
    if (key === 'profile') {
      setUserMenuOpen(false);
      setProfileOpen(true);
    } else if (key === 'logout') {
      logout();
    } else if (key.startsWith('goTo-') || key.startsWith('backTo-')) {
      setUserMenu(key.split('-')[1]);
    } else if (key.startsWith('theme-')) {
      changeTheme(key.replace('theme-', ''));
      setUserMenuOpen(false);
      setUserMenu('main');
    }
  };

  const header = (
    <Flex justify="space-between" style={{ backgroundColor: colors.header, padding: 16, width: '100%', boxShadow: palette.boxShadow }}>
      <Flex align="center" justify="center" gap={16} style={{ marginLeft: isMobile ? 8 : 24 }}>
        {isMobile && <Button shape="circle" icon={<MenuOutlined />} onClick={() => setDrawer(true)} />}
        {!me.admin && !isMobile && (
          <Flex align="center">
            <Tooltip title="Tổ chức của bạn">
              <Button type="link" style={{ color: colors.linkText, fontWeight: 500 }} onClick={() => me.organizationId && navigate('/organization?tab=info')}>
                {me.organizationName ?? 'Chưa tham gia tổ chức'}
              </Button>
            </Tooltip>
            <Typography.Text style={{ marginRight: 16, color: colors.textContrast }}>|</Typography.Text>
            <Typography.Text style={{ color: colors.textContrast }}>{roleText}</Typography.Text>
          </Flex>
        )}
        {me.admin && (
          <Tooltip title="Quyền">
            <Badge color="#0D5BB5" count="Admin" />
          </Tooltip>
        )}
      </Flex>
      <Flex align="center" gap={8} style={{ marginRight: 8 }}>
        <Dropdown
          open={userMenuOpen}
          onOpenChange={(open) => {
            setUserMenuOpen(open);
            if (!open) setUserMenu('main');
          }}
          trigger={['click']}
          placement="bottomRight"
          arrow
          menu={{ items: userItems, onClick: onUserMenu }}
        >
          <Button shape="circle" icon={<User size={16} />} size="large" aria-label={me.fullName} title={me.fullName} />
        </Dropdown>
      </Flex>
    </Flex>
  );

  const logoBlock = (
    <Link to="/">
      <Flex style={{ padding: collapsed && !isMobile ? 24 : 28 }} align="center" justify="center">
        <Logo size="small" light={lightLogo} />
      </Flex>
    </Link>
  );

  const body = (
    <Flex vertical style={{ padding: screens.xxl ? '28px 42px' : '28px 32px', backgroundColor: colors.frame, boxShadow: palette.boxShadow, flexGrow: 1 }}>
      <div style={{ background: palette.gray.white, padding: '28px 32px', borderRadius: spacing.borderRadius.xl, boxShadow: palette.boxShadow, flexGrow: 1 }}>
        <Routes>
          {pages
            .filter((p) => !p.menuOnly)
            .map((p) => (
              <Route
                key={p.path}
                path={p.path}
                element={p.visible(me, can) ? p.element : <Result status="403" title="403" subTitle="Bạn không có quyền xem trang này." />}
              />
            ))}
          <Route
            path="*"
            element={<Result status="404" title="404" subTitle="Không tìm thấy trang." extra={<Typography.Link onClick={() => navigate('/')}>Về trang chủ</Typography.Link>} />}
          />
        </Routes>
      </div>
    </Flex>
  );

  return (
    <Layout style={{ minHeight: '100vh' }}>
      {isMobile ? (
        <Layout>
          {header}
          <Drawer open={drawer} placement="left" width={260} onClose={() => setDrawer(false)} styles={{ body: { padding: 0, background: colors.sidebar } }} className="app-sidebar">
            {logoBlock}
            {sideMenu}
          </Drawer>
          <Content style={{ display: 'flex', flexDirection: 'column' }}>{body}</Content>
        </Layout>
      ) : (
        <>
          <Sider
            className="app-sidebar"
            theme={colors.themeSidebar}
            collapsible
            collapsed={collapsed}
            onCollapse={setCollapsed}
            width={260}
            style={{ overflow: 'auto', height: '100vh', position: 'fixed', left: 0, top: 0, bottom: 0, boxShadow: palette.boxShadow, background: colors.sidebar }}
          >
            {logoBlock}
            <Flex vertical style={{ padding: '0 8px', height: 'calc(100% - 100px)' }}>
              {sideMenu}
            </Flex>
          </Sider>
          <Layout style={{ marginLeft: collapsed ? 80 : 260, transition: 'margin-left .2s' }}>
            <Content style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
              {header}
              {body}
            </Content>
          </Layout>
        </>
      )}
      <ProfileModal open={profileOpen} onClose={() => setProfileOpen(false)} />
    </Layout>
  );
};

export default AppLayout;
