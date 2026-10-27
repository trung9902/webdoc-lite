package vn.webdoc.lite.service;

import java.util.LinkedHashSet;
import java.util.Set;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import vn.webdoc.lite.domain.Permission;
import vn.webdoc.lite.domain.UserAccount;

/**
 * Nơi duy nhất tính "quyền hiệu lực" của một người dùng = quyền của các vai trò + quyền bổ sung riêng.
 * Phân hệ mới (ví dụ Hỏi đáp và phân tích) nên gọi lại lớp này, không tự định nghĩa quyền.
 */
@Service
public class PermissionService {

    @Transactional(readOnly = true)
    public Set<String> effective(UserAccount user) {
        Set<String> names = new LinkedHashSet<>();
        user.getRoles().forEach(role -> role.getPermissions().stream().map(Permission::getName).forEach(names::add));
        user.getExtraPermissions().stream().map(Permission::getName).forEach(names::add);
        return names;
    }

    @Transactional(readOnly = true)
    public boolean has(UserAccount user, String permission) {
        return effective(user).contains(permission);
    }
}
