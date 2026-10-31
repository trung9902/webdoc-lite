import { BuildingOffice, Folders, House, Robot, UserGear } from '@phosphor-icons/react';

import AgentPage from './pages/AgentPage';
import DocumentsPage from './pages/DocumentsPage';
import HomePage from './pages/HomePage';
import OrganizationPage from './pages/OrganizationPage';
import PermissionsPage from './pages/PermissionsPage';
import UsersPage from './pages/UsersPage';

/** Nhóm menu con (hiện thành mục cha có mũi tên, giống bản WebDoc đầy đủ). */
export const groups = {
  admin: { label: 'Quản trị viên', icon: <UserGear size={20} /> },
  org: { label: 'Đơn vị của tôi', icon: <BuildingOffice size={20} /> },
};

const hasOrg = (me) => Boolean(me.organizationId);
const isAdmin = (me) => Boolean(me.admin);

/**
 * DANH SÁCH TRANG DUY NHẤT của ứng dụng. Mỗi phần tử vừa sinh ra một mục menu, vừa sinh ra một đường dẫn.
 *
 * Thêm trang mới (ví dụ "Hỏi đáp và phân tích"):
 *   1. Viết component trong src/pages.
 *   2. Thêm một phần tử vào mảng dưới đây.
 *   3. `visible(me, can)` quyết định hiện/ẩn menu VÀ chặn truy cập trực tiếp bằng đường dẫn.
 *      Ví dụ chỉ hiện với người có quyền tra cứu hoặc phân tích:
 *        visible: (me, can) => can('gaa.search') || can('gaa.analytics')
 *   4. Muốn mục nằm trong menu con thì thêm `group: 'admin'` hoặc `group: 'org'` (xem `groups` ở trên).
 *   5. Mục menu trỏ tới đường dẫn có query thì đặt `to: '/organization?tab=users'`; mục chỉ để điều hướng,
 *      dùng chung trang đã có, đặt thêm `menuOnly: true` (không sinh thêm đường dẫn).
 *
 * Lưu ý: ẩn menu chỉ là tiện lợi. Quyền thật luôn do backend kiểm tra.
 */
export const pages = [
  { path: '/', label: 'Trang chủ', icon: <House size={20} />, element: <HomePage />, visible: () => true },

  { path: '/admin/organizations', label: 'Quản lý tổ chức', group: 'admin', element: <OrganizationPage />, visible: isAdmin },
  { path: '/admin/users', label: 'Quản lý người dùng', group: 'admin', element: <UsersPage />, visible: isAdmin },
  { path: '/admin/permissions', label: 'Phân quyền', group: 'admin', element: <PermissionsPage />, visible: isAdmin },

  { path: '/organization', to: '/organization?tab=info', label: 'Thông tin chung', group: 'org', element: <OrganizationPage />, visible: hasOrg },
  { path: '/organization', to: '/organization?tab=departments', label: 'Phòng ban', group: 'org', menuOnly: true, visible: hasOrg },
  { path: '/organization', to: '/organization?tab=users', label: 'Thành viên', group: 'org', menuOnly: true, visible: hasOrg },

  { path: '/documents', label: 'Quản lý tài liệu', icon: <Folders size={20} />, element: <DocumentsPage />, visible: () => true },

  { path: '/agent', label: 'Hỏi đáp Agent', icon: <Robot size={20} />, element: <AgentPage />, visible: () => true },
];
