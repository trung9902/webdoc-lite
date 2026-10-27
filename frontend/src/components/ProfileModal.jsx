import { Descriptions, Form, Input, message, Modal, Select } from 'antd';
import { useEffect, useState } from 'react';

import api, { errorMessage } from '../api/client';
import { useAuth } from '../auth/AuthContext';

/** "Thông tin tài khoản": xem thông tin và sửa họ tên, giới tính (PUT /users/profile). */
const ProfileModal = ({ open, onClose }) => {
  const { me, reload } = useAuth();
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open) form.setFieldsValue({ lastName: me.lastName, firstName: me.firstName, gender: me.gender ?? undefined });
  }, [open, me, form]);

  const save = async (values) => {
    setSaving(true);
    try {
      await api.put('/users/profile', values);
      await reload();
      message.success('Đã cập nhật thông tin tài khoản');
      onClose();
    } catch (e) {
      message.error(errorMessage(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal open={open} title="Thông tin tài khoản" okText="Lưu" cancelText="Huỷ" confirmLoading={saving} onCancel={onClose} onOk={() => form.submit()} destroyOnClose>
      <Descriptions column={1} size="small" style={{ marginBottom: 16 }}>
        <Descriptions.Item label="Tên đăng nhập">{me.username}</Descriptions.Item>
        <Descriptions.Item label="Email">{me.email}</Descriptions.Item>
        <Descriptions.Item label="Tổ chức">{me.organizationName || '—'}</Descriptions.Item>
        <Descriptions.Item label="Phòng ban">{me.departmentName || '—'}</Descriptions.Item>
      </Descriptions>
      <Form form={form} layout="vertical" onFinish={save}>
        <Form.Item name="lastName" label="Họ và tên đệm" rules={[{ required: true, message: 'Nhập họ và tên đệm' }, { max: 30, message: 'Tối đa 30 ký tự' }]}>
          <Input />
        </Form.Item>
        <Form.Item name="firstName" label="Tên" rules={[{ required: true, message: 'Nhập tên' }, { max: 30, message: 'Tối đa 30 ký tự' }]}>
          <Input />
        </Form.Item>
        <Form.Item name="gender" label="Giới tính">
          <Select
            allowClear
            options={[
              { value: true, label: 'Nam' },
              { value: false, label: 'Nữ' },
            ]}
          />
        </Form.Item>
      </Form>
    </Modal>
  );
};

export default ProfileModal;
