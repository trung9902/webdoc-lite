import { RobotOutlined, SendOutlined } from '@ant-design/icons';
import { Alert, Button, Card, Input, Space, Spin, Typography } from 'antd';
import { useState } from 'react';

import api, { errorMessage } from '../api/client';

const AgentPage = () => {
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const ask = async () => {
    const q = question.trim();
    if (!q) return;

    setLoading(true);
    setError(null);
    setAnswer(null);
    try {
      const { data } = await api.get('/agent/ask', { params: { q } });
      setAnswer(data.answer);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Typography.Title level={3} style={{ margin: 0 }}>
        <RobotOutlined style={{ marginRight: 8 }} />
        Hỏi đáp Agent
      </Typography.Title>

      <Space.Compact style={{ width: '100%', maxWidth: 600 }}>
        <Input
          placeholder="Nhập câu hỏi của bạn..."
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onPressEnter={ask}
          disabled={loading}
          allowClear
        />
        <Button type="primary" icon={<SendOutlined />} onClick={ask} loading={loading}>
          Hỏi agent
        </Button>
      </Space.Compact>

      {loading && <Spin tip="Đang xử lý..." />}

      {error && <Alert type="error" showIcon message="Lỗi" description={error} />}

      {answer && (
        <Card title="Câu trả lời" size="small" style={{ maxWidth: 600 }}>
          <Typography.Paragraph style={{ whiteSpace: 'pre-wrap', margin: 0 }}>{answer}</Typography.Paragraph>
        </Card>
      )}
    </Space>
  );
};

export default AgentPage;
