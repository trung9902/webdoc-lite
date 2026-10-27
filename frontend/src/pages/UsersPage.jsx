import { MoreOutlined } from '@ant-design/icons';
import { Button, Checkbox, Dropdown, Form, Input, message, Modal, Select, Space, Switch, Table, Tag, Typography } from 'antd';
import { useCallback, useEffect, useState } from 'react';

import api, { errorMessage } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { formatDateTime } from '../utils/format';

const UsersPage = () => {
  const { me } = useAuth();
  const [form] = Form.useForm();
  const [q, setQ] = useState('');
  const [page, setPage] = useState(0);
  const [data, setData] = useState({ list: [], total: 0 });
  const [loading, setLoading] = useState(false);
  const [roles, setRoles] = useState([]);
  const [perms, setPerms] = useState([]);
  const [depts, setDepts] = useState([]);
  const [editing, setEditing] = useState(null);
  const [permUser, setPermUser] = useState(null);
  const [extra, setExtra] = useState([]);

  const load = useCallback(
    async (p = 0) => {
      setLoading(true);
      try {
        const { data: res } = await api.get('/users/filter', { params: { q: q || undefined, page: p, size: 10 } });

        setData(res);
        setPage(p);
      } catch (e) {
        message.error(errorMessage(e));
      } finally {
        setLoading(false);
      }
    },
    [q],
  );

  useEffect(() => {
    load(0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    Promise.all([api.get('/roles'), api.get('/permissions'), api.get(`/departments/organization/${me.organizationId}`)])
      .then(([r, p, d]) => {
        setRoles(r.data);
        setPerms(p.data);
        setDepts(d.data);
      })
      .catch((e) => message.error(errorMessage(e)));
  }, [me.organizationId]);

  const openEditor = (record) => {
    setEditing(record || {});
    form.resetFields();
    form.setFieldsValue(
      record
        ? {
            email: record.email,
            lastName: record.lastName,
            firstName: record.firstName,
            roleCodes: record.roleCodes,
            departmentId: record.deptId,
            areas: record.areas,
            mfaEnabled: record.mfa,
            organizationManager: record.organizationManager,
          }
        : { roleCodes: ['MEMBER'], areas: [], mfaEnabled: false, organizationManager: false },
    );
  };

  const save = async (values) => {
    const body = { ...values, organizationId: me.organizationId };

    try {
      if (editing.id) await api.put(`/users/${editing.id}`, body);
      else await api.post('/users', body);
      message.success('Đã lưu người dùng');
      setEditing(null);
      load(page);
    } catch (e) {
      message.error(errorMessage(e));
    }
  };

  const act = async (fn, okText) => {
    try {
      await fn();
      message.success(okText);
      load(page);
    } catch (e) {
      message.error(errorMessage(e));
    }
  };

  const openPerms = (record) => {
    const fromRoles = new Set(record.roleCodes.flatMap((c) => roles.find((r) => r.code === c)?.permissionNames || []));

    setPermUser(record);
    setExtra(record.permissionNames.filter((n) => !fromRoles.has(n)));
  };

  const savePerms = async () => {
    try {
      await api.put(`/users/${permUser.id}/permissions`, { permissionNames: extra });
      message.success('Đã lưu quyền bổ sung');
      setPermUser(null);
      load(page);
    } catch (e) {
      message.error(errorMessage(e));
    }
  };

  const columns = [
    { title: 'Tên đăng nhập', dataIndex: 'username' },
    { title: 'Họ và tên', dataIndex: 'fullName' },
    { title: 'Vai trò', dataIndex: 'roleNames', render: (v) => v.map((r) => <Tag key={r}>{r}</Tag>) },
    { title: 'Phòng ban', dataIndex: 'departmentName', render: (v) => v || '—' },
    { title: 'Phường (ABAC)', dataIndex: 'areas', render: (v) => (v.length ? v.map((a) => <Tag key={a}>{a}</Tag>) : '—') },
    { title: 'MFA', dataIndex: 'mfa', render: (v) => (v ? 'Có' : 'Không') },
    { title: 'Trạng thái', dataIndex: 'status', render: (v) => (v === 1 ? <Tag color="green">Hoạt động</Tag> : <Tag color="red">Bị khoá</Tag>) },
    { title: 'Tạo lúc', dataIndex: 'createdAt', render: formatDateTime },
    {
      title: 'Hành động',
      fixed: 'right',
      render: (_, r) => (
        <Dropdown
          trigger={['click']}
          menu={{
            items: [
              { key: 'edit', label: 'Sửa thông tin', onClick: () => openEditor(r) },
              { key: 'perm', label: 'Quyền bổ sung', onClick: () => openPerms(r) },
              {
                key: 'admin',
                label: r.admin ? 'Gỡ quyền quản trị' : 'Cấp quyền quản trị',
                onClick: () => act(() => api.put('/users/role', { userId: r.id, admin: !r.admin }), 'Đã đổi quyền quản trị'),
              },
              {
                key: 'status',
                danger: r.status === 1,
                label: r.status === 1 ? 'Khoá tài khoản' : 'Mở khoá',
                onClick: () => act(() => api.put('/users/status', { userId: r.id, status: r.status === 1 ? 2 : 1 }), 'Đã đổi trạng thái'),
              },
            ],
          }}
        >
          <Button type="text" icon={<MoreOutlined />} aria-label="Hành động" />
        </Dropdown>
      ),
    },
  ];

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Typography.Title level={3} style={{ margin: 0 }}>
        Quản lý người dùng
      </Typography.Title>
      <Space>
        <Input.Search placeholder="Tìm theo tên đăng nhập, email, tên" allowClear style={{ width: 320 }} value={q} onChange={(e) => setQ(e.target.value)} onSearch={() => load(0)} />
        <Button type="primary" onClick={() => openEditor(null)}>
          Thêm người dùng
        </Button>
      </Space>
      <Table
        rowKey="id"
        size="small"
        loading={loading}
        columns={columns}
        dataSource={data.list}
        scroll={{ x: 1000 }}
        pagination={{ current: page + 1, pageSize: 10, total: data.total, showTotal: (t) => `${t} tài khoản`, onChange: (p) => load(p - 1) }}
      />

      <Modal open={Boolean(editing)} title={editing?.id ? 'Sửa người dùng' : 'Thêm người dùng'} okText="Lưu" cancelText="Huỷ" onCancel={() => setEditing(null)} onOk={() => form.submit()} destroyOnClose>
        <Form form={form} layout="vertical" onFinish={save}>
          {!editing?.id && (
            <Form.Item name="username" label="Tên đăng nhập" rules={[{ required: true, message: 'Nhập tên đăng nhập' }]}>
              <Input />
            </Form.Item>
          )}
          <Form.Item name="email" label="Email" rules={[{ required: true, type: 'email', message: 'Email không hợp lệ' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="password" label={editing?.id ? 'Mật khẩu mới (bỏ trống nếu giữ nguyên)' : 'Mật khẩu'} rules={editing?.id ? [] : [{ required: true, min: 8, message: 'Tối thiểu 8 ký tự' }]}>
            <Input.Password autoComplete="new-password" />
          </Form.Item>
          <Space style={{ display: 'flex' }} align="start">
            <Form.Item name="lastName" label="Họ và tên đệm" rules={[{ required: true, max: 30 }]}>
              <Input />
            </Form.Item>
            <Form.Item name="firstName" label="Tên" rules={[{ required: true, max: 30 }]}>
              <Input />
            </Form.Item>
          </Space>
          <Form.Item name="roleCodes" label="Vai trò">
            <Select mode="multiple" options={roles.map((r) => ({ value: r.code, label: r.name }))} />
          </Form.Item>
          <Form.Item name="departmentId" label="Phòng ban">
            <Select allowClear options={depts.map((d) => ({ value: d.id, label: d.name }))} />
          </Form.Item>
          <Form.Item name="areas" label="Phường được xem (để trống = tất cả)">
            <Select mode="tags" tokenSeparators={[',']} placeholder="Nhập tên phường rồi Enter" />
          </Form.Item>
          <Space size="large">
            <Form.Item name="mfaEnabled" label="Đã xác thực MFA" valuePropName="checked">
              <Switch />
            </Form.Item>
            <Form.Item name="organizationManager" label="Quản lý tổ chức" valuePropName="checked">
              <Switch />
            </Form.Item>
          </Space>
        </Form>
      </Modal>

      <Modal open={Boolean(permUser)} title={`Quyền bổ sung cho ${permUser?.username}`} okText="Lưu" cancelText="Huỷ" onCancel={() => setPermUser(null)} onOk={savePerms} destroyOnClose>
        <Typography.Paragraph type="secondary">Cộng thêm vào quyền đã có từ vai trò.</Typography.Paragraph>
        <Checkbox.Group value={extra} onChange={setExtra} style={{ display: 'grid', gap: 6 }} options={perms.map((p) => ({ value: p.name, label: `${p.name} - ${p.description || ''}` }))} />
      </Modal>
    </Space>
  );
};

export default UsersPage;
