import { Button, Checkbox, message, Space, Table, Typography } from 'antd';
import { useCallback, useEffect, useState } from 'react';

import api, { errorMessage } from '../api/client';

/** Ma trận quyền theo vai trò: mỗi hàng là một quyền, mỗi cột là một vai trò. */
const PermissionsPage = () => {
  const [roles, setRoles] = useState([]);
  const [perms, setPerms] = useState([]);
  const [grant, setGrant] = useState({}); // roleId -> Set tên quyền
  const [dirty, setDirty] = useState(new Set());
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const [r, p] = await Promise.all([api.get('/roles'), api.get('/permissions')]);

      setRoles(r.data);
      setPerms(p.data);
      setGrant(Object.fromEntries(r.data.map((x) => [x.id, new Set(x.permissionNames)])));
      setDirty(new Set());
    } catch (e) {
      message.error(errorMessage(e));
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const toggle = (roleId, name, on) => {
    const next = new Set(grant[roleId]);

    if (on) next.add(name);
    else next.delete(name);
    setGrant({ ...grant, [roleId]: next });
    setDirty(new Set(dirty).add(roleId));
  };

  const save = async () => {
    setSaving(true);
    try {
      await Promise.all([...dirty].map((id) => api.put(`/roles/${id}/permissions`, { permissionNames: [...grant[id]] })));
      message.success('Đã lưu phân quyền. Có hiệu lực từ yêu cầu kế tiếp của người dùng.');
      await load();
    } catch (e) {
      message.error(errorMessage(e));
    } finally {
      setSaving(false);
    }
  };

  const columns = [
    {
      title: 'Quyền',
      render: (_, p) => (
        <div>
          <Typography.Text strong>{p.name}</Typography.Text>
          <div>
            <Typography.Text type="secondary">{p.description}</Typography.Text>
          </div>
        </div>
      ),
    },
    { title: 'Nhóm', dataIndex: 'groupName', width: 140 },
    ...roles.map((r) => ({
      title: r.name,
      align: 'center',
      width: 140,
      render: (_, p) => <Checkbox checked={grant[r.id]?.has(p.name) || false} onChange={(e) => toggle(r.id, p.name, e.target.checked)} />,
    })),
  ];

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Typography.Title level={3} style={{ margin: 0 }}>
        Phân quyền theo vai trò
      </Typography.Title>
      <Table rowKey="id" size="small" columns={columns} dataSource={perms} pagination={false} />
      <Space>
        <Button onClick={load} disabled={!dirty.size}>
          Huỷ thay đổi
        </Button>
        <Button type="primary" onClick={save} loading={saving} disabled={!dirty.size}>
          Lưu phân quyền
        </Button>
      </Space>
    </Space>
  );
};

export default PermissionsPage;
