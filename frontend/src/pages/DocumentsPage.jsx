import { Button, DatePicker, Descriptions, Drawer, Form, Input, InputNumber, Select, Space, Table, Tag, Typography } from 'antd';
import { useCallback, useEffect, useState } from 'react';

import api, { errorMessage } from '../api/client';
import { formatDateTime, formatNumber } from '../utils/format';

const STATUS = { PUBLISHED: ['Đã ban hành', 'green'], DRAFT: ['Bản nháp', 'orange'] };

const DocumentsPage = () => {
  const [form] = Form.useForm();
  const [data, setData] = useState({ list: [], total: 0 });
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [detail, setDetail] = useState(null);

  const load = useCallback(
    async (nextPage = 0) => {
      const v = form.getFieldsValue();

      setLoading(true);
      setError(null);
      try {
        const { data: res } = await api.get('/documents/filter', {
          params: {
            q: v.q || undefined,
            text: v.text || undefined,
            type: v.type || undefined,
            area: v.area || undefined,
            maxSizeKb: v.maxSizeKb ?? undefined,
            from: v.range?.[0]?.format('YYYY-MM-DD'),
            to: v.range?.[1]?.format('YYYY-MM-DD'),
            page: nextPage,
            size: 10,
          },
        });

        setData(res);
        setPage(nextPage);
      } catch (e) {
        setError(errorMessage(e));
      } finally {
        setLoading(false);
      }
    },
    [form],
  );

  useEffect(() => {
    load(0);
  }, [load]);

  const open = async (id) => {
    try {
      const { data: res } = await api.get(`/documents/${id}`);

      setDetail(res);
    } catch (e) {
      setError(errorMessage(e));
    }
  };

  const columns = [
    { title: 'Tên tệp', dataIndex: 'originalFilename', render: (v, r) => <a onClick={() => open(r.id)}>{v}</a> },
    { title: 'Tiêu đề', dataIndex: 'title' },
    { title: 'Loại', dataIndex: 'type', width: 70 },
    { title: 'Dung lượng (KB)', dataIndex: 'sizeKb', align: 'right', render: (v) => formatNumber(v) },
    { title: 'Phường', dataIndex: 'area', render: (v) => v || '—' },
    { title: 'Phòng ban', dataIndex: 'departmentName', render: (v) => v || '—' },
    { title: 'Người tạo', dataIndex: 'createdBy' },
    { title: 'Ngày tạo', dataIndex: 'createdAt', render: formatDateTime },
    {
      title: 'Trạng thái',
      dataIndex: 'status',
      render: (v, r) => (
        <Space size={4}>
          <Tag color={(STATUS[v] || [])[1]}>{(STATUS[v] || [v])[0]}</Tag>
          {r.accessLevel === 'PRIVATE' && <Tag color="red">Riêng tư</Tag>}
        </Space>
      ),
    },
  ];

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Typography.Title level={3} style={{ margin: 0 }}>
        Tài liệu
      </Typography.Title>
      <Form form={form} layout="inline" onFinish={() => load(0)} style={{ rowGap: 8 }}>
        <Form.Item name="q">
          <Input placeholder="Tên tệp hoặc tiêu đề" allowClear style={{ width: 200 }} />
        </Form.Item>
        <Form.Item name="text">
          <Input placeholder="Tìm trong nội dung" allowClear style={{ width: 180 }} />
        </Form.Item>
        <Form.Item name="type">
          <Select placeholder="Loại" allowClear style={{ width: 100 }} options={['pdf', 'png', 'docx', 'xlsx'].map((t) => ({ value: t, label: t }))} />
        </Form.Item>
        <Form.Item name="area">
          <Input placeholder="Phường" allowClear style={{ width: 130 }} />
        </Form.Item>
        <Form.Item name="maxSizeKb" tooltip="Dưới giá trị này (không gồm đúng bằng)">
          <InputNumber placeholder="Dưới ... KB" min={0} style={{ width: 120 }} />
        </Form.Item>
        <Form.Item name="range">
          <DatePicker.RangePicker format="DD/MM/YYYY" />
        </Form.Item>
        <Button type="primary" htmlType="submit">
          Tìm
        </Button>
        <Button
          style={{ marginLeft: 8 }}
          onClick={() => {
            form.resetFields();
            load(0);
          }}
        >
          Đặt lại
        </Button>
      </Form>
      {error && <Typography.Text type="danger">{error}</Typography.Text>}
      <Table
        rowKey="id"
        size="small"
        loading={loading}
        columns={columns}
        dataSource={data.list}
        scroll={{ x: 1000 }}
        pagination={{
          current: page + 1,
          pageSize: 10,
          total: data.total,
          showTotal: (t) => `${formatNumber(t, 0)} tài liệu`,
          onChange: (p) => load(p - 1),
        }}
      />
      <Drawer open={Boolean(detail)} onClose={() => setDetail(null)} width={560} title={detail?.info.title}>
        {detail && (
          <Space direction="vertical" style={{ width: '100%' }}>
            <Descriptions column={1} size="small" bordered>
              <Descriptions.Item label="Tên tệp">{detail.info.originalFilename}</Descriptions.Item>
              <Descriptions.Item label="Dung lượng">{formatNumber(detail.info.sizeKb)} KB</Descriptions.Item>
              <Descriptions.Item label="Số trang">{detail.info.pageCount || '—'}</Descriptions.Item>
              <Descriptions.Item label="Phường">{detail.info.area || '—'}</Descriptions.Item>
              <Descriptions.Item label="Mã băm nội dung">
                <Typography.Text code style={{ wordBreak: 'break-all' }}>
                  {detail.info.contentHash || '—'}
                </Typography.Text>
              </Descriptions.Item>
            </Descriptions>
            {detail.pages.map((text, i) => (
              <div key={text.slice(0, 40) + i}>
                <Typography.Text strong>Trang {i + 1}</Typography.Text>
                <Typography.Paragraph style={{ background: '#fafafa', padding: 8, marginTop: 4 }}>{text}</Typography.Paragraph>
              </div>
            ))}
          </Space>
        )}
      </Drawer>
    </Space>
  );
};

export default DocumentsPage;
