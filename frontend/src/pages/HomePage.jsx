import { Card, Descriptions, Space, Tag, Typography } from 'antd';

import { useAuth } from '../auth/AuthContext';

const HomePage = () => {
  const { me } = useAuth();

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Typography.Title level={3} style={{ margin: 0 }}>
        Xin chào, {me.fullName}
      </Typography.Title>
      <Card title="Thông tin tài khoản của bạn">
        <Descriptions column={1} size="small" bordered>
          <Descriptions.Item label="Tên đăng nhập">{me.username}</Descriptions.Item>
          <Descriptions.Item label="Tổ chức">{me.organizationName}</Descriptions.Item>
          <Descriptions.Item label="Phòng ban">{me.departmentName || '—'}</Descriptions.Item>
          <Descriptions.Item label="Vai trò">
            {me.roleNames.map((r) => (
              <Tag key={r} color="blue">
                {r}
              </Tag>
            ))}
          </Descriptions.Item>
          <Descriptions.Item label="Phường được xem (ABAC)">
            {me.areas.length ? me.areas.map((a) => <Tag key={a}>{a}</Tag>) : 'Không giới hạn'}
          </Descriptions.Item>
          <Descriptions.Item label="Xác thực 2 lớp (MFA)">{me.mfa ? 'Đã bật' : 'Chưa bật'}</Descriptions.Item>
          <Descriptions.Item label="Quyền hiệu lực">
            {me.permissionNames.length
              ? me.permissionNames.map((p) => (
                  <Tag key={p} color="green">
                    {p}
                  </Tag>
                ))
              : 'Không có quyền đặc biệt'}
          </Descriptions.Item>
        </Descriptions>
      </Card>
    </Space>
  );
};

export default HomePage;
