// Kiểm thử giao diện WebDoc Lite: đăng nhập từng tài khoản demo, kiểm tra menu theo quyền và vài thao tác chính.
const { open } = require('./lib');

const menuOf = (b) => b.ev(`[...document.querySelectorAll('.app-sidebar .ant-menu-item')].map(e=>e.textContent.trim())`);
const results = [];
const check = (name, ok, extra = '') => { results.push(ok); console.log(`${ok ? 'ĐẠT ' : 'LỖI '} ${name}${extra ? ' | ' + extra : ''}`); };

(async () => {
  const base = ['Trang chủ', 'Thông tin chung', 'Phòng ban', 'Thành viên', 'Quản lý tài liệu'];
  const accounts = {
    'qtkt.gd2': ['Trang chủ', 'Quản lý tổ chức', 'Quản lý người dùng', 'Phân quyền', 'Thông tin chung', 'Phòng ban', 'Thành viên', 'Quản lý tài liệu'],
    'qtdl.gd2': base,
    'capnhat.ht': base,
    'doichieu.ds': base,
    'khaithac.so': base,
  };
  for (const [user, expected] of Object.entries(accounts)) {
    const b = await open();
    await b.login(user, 'Demo@123');
    const menu = await menuOf(b);
    check(`[${user}] menu theo vai trò`, JSON.stringify(menu) === JSON.stringify(expected), menu.join(' | '));
    check(`[${user}] không có lỗi JS`, b.log.errors.filter((e) => /^EXC/.test(e)).length === 0);
    if (user === 'doichieu.ds') {
      await b.goto('/documents', 3500);
      const areas = await b.ev(`[...document.querySelectorAll('.ant-table-tbody tr.ant-table-row')].map(r=>r.children[4].textContent.trim())`);
      check('[doichieu.ds] danh sách tài liệu chỉ có phường Đông Sơn', areas.length > 0 && areas.every((a) => a === 'Đông Sơn'), `${areas.length} dòng`);
    }
    if (user === 'khaithac.so') {
      await b.goto('/admin/users', 3000);
      check('[khaithac.so] vào thẳng /admin/users bị chặn 403', (await b.text()).includes('Bạn không có quyền xem trang này'));
      await b.goto('/documents', 3500);
      await b.type('input[placeholder="Dưới ... KB"]', '100');
      await b.click('button', 'Tìm'); await b.sleep(1500);
      const sizes = await b.ev(`[...document.querySelectorAll('.ant-table-tbody tr.ant-table-row')].map(r=>parseFloat(r.children[3].textContent.replace(/\s/g,'').replace(',','.')))`);
      check('[khaithac.so] lọc "dưới 100 KB" chỉ ra tệp nhỏ hơn 100 KB', sizes.length > 0 && sizes.every((x) => x < 100), `${sizes.length} dòng, lớn nhất ${Math.max(...sizes)} KB`);
    }
    if (user === 'qtkt.gd2') {
      await b.goto('/admin/users', 3500);
      const rows = await b.ev(`document.querySelectorAll('.ant-table-tbody tr.ant-table-row').length`);
      check('[qtkt.gd2] bảng người dùng có dữ liệu', rows >= 5, `${rows} dòng`);
      await b.click('button .anticon-more'); await b.sleep(500);
      const items = await b.ev(`[...document.querySelectorAll('.ant-dropdown-menu-item')].map(e=>e.textContent.trim())`);
      check('[qtkt.gd2] cột Hành động xổ ra menu', items.length >= 4, items.join(' | '));
      await b.shot('lite_users');
      await b.goto('/admin/permissions', 3500);
      const boxes = await b.ev(`document.querySelectorAll('.ant-checkbox-input').length`);
      check('[qtkt.gd2] ma trận phân quyền hiển thị', boxes === 21, `${boxes} ô tick (7 quyền x 3 vai trò)`);
      await b.shot('lite_permissions');
      await b.goto('/organization?tab=users', 3000);
      const members = await b.ev(`document.querySelectorAll('.ant-table-tbody tr.ant-table-row').length`);
      check('[qtkt.gd2] tab Thành viên (?tab=users) có dữ liệu', members >= 5, `${members} dòng`);
      await b.shot('lite_members');
    }
    b.close();
  }
  console.log(`\nTổng: ${results.filter(Boolean).length}/${results.length} đạt`);
  process.exit(results.every(Boolean) ? 0 : 1);
})();
