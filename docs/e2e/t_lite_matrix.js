// Quản trị bỏ tick một quyền trên màn hình phân quyền; người dùng mất quyền ngay ở yêu cầu kế tiếp (cùng token), rồi khôi phục.
const { open } = require('./lib');

const API = 'http://localhost:8098/api/v1';
const login = async (u, p = 'Demo@123') =>
  (await (await fetch(`${API}/auth/login`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email: u, password: p }) })).json()).access_token;
const perms = async (token) =>
  (await (await fetch(`${API}/users/profile`, { headers: { Authorization: `Bearer ${token}` } })).json()).permissionNames;

(async () => {
  const member = await login('khaithac.so');
  const before = await perms(member);
  console.log('trước :', before.sort().join(', '));

  const b = await open();
  await b.login('qtkt.gd2', 'Demo@123');
  await b.goto('/admin/permissions', 3500);
  const toggle = () => b.clickWithin('tr.ant-table-row', 'gaa.analytics', 'td:nth-child(5) .ant-checkbox-input');
  console.log('bỏ tick :', await toggle());
  await b.click('button', 'Lưu phân quyền'); await b.sleep(1500);
  const during = await perms(member);
  console.log('sau lưu:', during.sort().join(', '));
  const ok1 = before.includes('gaa.analytics') && !during.includes('gaa.analytics');

  console.log('tick lại :', await toggle());
  await b.click('button', 'Lưu phân quyền'); await b.sleep(1500);
  const after = await perms(member);
  console.log('khôi phục:', after.sort().join(', '));
  const ok2 = after.includes('gaa.analytics');
  b.close();
  console.log(ok1 && ok2 ? 'ĐẠT: thu hồi và khôi phục quyền có hiệu lực ngay, không cần đăng nhập lại' : 'LỖI');
  process.exit(ok1 && ok2 ? 0 : 1);
})();
