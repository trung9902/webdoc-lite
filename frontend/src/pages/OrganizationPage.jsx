import { Button, Descriptions, Form, Input, message, Modal, Popconfirm, Select, Space, Table, Tabs, Typography } from 'antd';
import { useCallback, useEffect, useState } from 'react';
import { useLocation, useSearchParams } from 'react-router-dom';

import api, { errorMessage } from '../api/client';
import { useAuth } from '../auth/AuthContext';

const OrganizationPage = () => {
  const { me } = useAuth();
  const [form] = Form.useForm();
  const [params, setParams] = useSearchParams();
  const adminView = useLocation().pathname.startsWith('/admin');
  const tab = ['info', 'departments', 'users'].includes(params.get('tab')) ? params.get('tab') : 'info';
  const [orgs, setOrgs] = useState([]);
  const [orgId, setOrgId] = useState(me.organizationId);
  const [depts, setDepts] = useState([]);
  const [members, setMembers] = useState([]);
  const [editing, setEditing] = useState(null);

  const canManage = me.admin || me.organizationManager;

  useEffect(() => {
    api
      .get('/organizations')
      .then(({ data }) => {
        setOrgs(data);
        setOrgId((current) => current ?? data[0]?.id);
      })
      .catch((e) => message.error(errorMessage(e)));
  }, []);

  useEffect(() => {
    if (!orgId) return;
    api
      .get('/users/filter', { params: { organizationId: orgId, page: 0, size: 100 } })
      .then(({ data }) => setMembers(data.list))
      .catch((e) => message.error(errorMessage(e)));
  }, [orgId]);

  const loadDepts = useCallback(async () => {
    if (!orgId) return;
    try {
      const { data } = await api.get(`/departments/organization/${orgId}`);

      setDepts(data);
    } catch (e) {
      message.error(errorMessage(e));
    }
  }, [orgId]);

  useEffect(() => {
    loadDepts();
  }, [loadDepts]);

  const org = orgs.find((o) => o.id === orgId);

  const openEditor = (record) => {
    setEditing(record || {});
    form.setFieldsValue({ name: record?.name, description: record?.description });
  };

  const save = async (values) => {
    try {
      if (editing.id) await api.put(`/departments/${editing.id}`, { ...values, organizationId: orgId });
      else await api.post('/departments', { ...values, organizationId: orgId });
      message.success('Đã lưu phòng ban');
      setEditing(null);
      loadDepts();
    } catch (e) {
      message.error(errorMessage(e));
    }
  };

  const remove = async (id) => {
    try {
      await api.delete(`/departments/${id}`);
      message.success('Đã xoá phòng ban');
      loadDepts();
    } catch (e) {
      message.error(errorMessage(e));
    }
  };

  const columns = [
    { title: 'Tên phòng ban', dataIndex: 'name' },
    { title: 'Mô tả', dataIndex: 'description' },
    ...(canManage
      ? [
          {
            title: 'Hành động',
            width: 160,
            render: (_, r) => (
              <Space>
                <a onClick={() => openEditor(r)}>Sửa</a>
                <Popconfirm title="Xoá phòng ban này?" okText="Xoá" cancelText="Huỷ" onConfirm={() => remove(r.id)}>
                  <a style={{ color: '#cf1322' }}>Xoá</a>
                </Popconfirm>
              </Space>
            ),
          },
        ]
      : []),
  ];

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Typography.Title level={3} style={{ margin: 0 }}>
        {adminView ? 'Quản lý tổ chức' : 'Đơn vị của tôi'}
      </Typography.Title>
      {me.admin && orgs.length > 1 && (
        <Select style={{ width: 320 }} value={orgId} onChange={setOrgId} options={orgs.map((o) => ({ value: o.id, label: o.name }))} />
      )}
      <Tabs
        activeKey={tab}
        onChange={(key) => setParams({ tab: key })}
        items={[
          {
            key: 'info',
            label: 'Thông tin chung',
            children: org ? (
              <Descriptions bordered size="small" column={1}>
                <Descriptions.Item label="Mã">{org.code}</Descriptions.Item>
                <Descriptions.Item label="Tên">{org.name}</Descriptions.Item>
                <Descriptions.Item label="Mô tả">{org.description || '—'}</Descriptions.Item>
              </Descriptions>
            ) : null,
          },
          {
            key: 'departments',
            label: 'Phòng ban',
            children: (
              <Space direction="vertical" style={{ width: '100%' }}>
                {canManage && (
                  <Button type="primary" onClick={() => openEditor(null)}>
                    Tạo phòng ban
                  </Button>
                )}
                <Table rowKey="id" size="small" columns={columns} dataSource={depts} pagination={false} />
              </Space>
            ),
          },
          {
            key: 'users',
            label: 'Thành viên',
            children: (
              <Table
                rowKey="id"
                size="small"
                dataSource={members}
                pagination={false}
                columns={[
                  { title: 'Họ và tên', dataIndex: 'fullName' },
                  { title: 'Tên đăng nhập', dataIndex: 'username' },
                  { title: 'Email', dataIndex: 'email' },
                  { title: 'Phòng ban', dataIndex: 'departmentName', render: (v) => v || '—' },
                  { title: 'Vai trò', dataIndex: 'roleNames', render: (v) => (v || []).join(', ') || '—' },
                ]}
              />
            ),
          },
        ]}
      />
      <Modal open={Boolean(editing)} title={editing?.id ? 'Sửa phòng ban' : 'Tạo phòng ban'} okText="Lưu" cancelText="Huỷ" onCancel={() => setEditing(null)} onOk={() => form.submit()} destroyOnClose>
        <Form form={form} layout="vertical" onFinish={save}>
          <Form.Item name="name" label="Tên phòng ban" rules={[{ required: true, message: 'Nhập tên phòng ban' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="description" label="Mô tả">
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  );
};

export default OrganizationPage;
