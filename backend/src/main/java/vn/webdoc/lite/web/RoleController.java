package vn.webdoc.lite.web;

import java.util.List;

import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import vn.webdoc.lite.service.RoleService;
import vn.webdoc.lite.web.Dtos.PermissionResponse;
import vn.webdoc.lite.web.Dtos.PermissionsRequest;
import vn.webdoc.lite.web.Dtos.RoleResponse;

/** Màn hình phân quyền: danh sách quyền, danh sách vai trò và ma trận quyền theo vai trò. Chỉ quản trị viên. */
@RestController
@RequestMapping("/api/v1")
@RequiredArgsConstructor
@PreAuthorize("hasRole('SYSTEM_ADMIN')")
public class RoleController {
    private final RoleService roles;

    @GetMapping("/permissions")
    public List<PermissionResponse> permissions() {
        return roles.listPermissions();
    }

    @GetMapping("/roles")
    public List<RoleResponse> roles() {
        return roles.listRoles();
    }

    @PutMapping("/roles/{id}/permissions")
    public RoleResponse setPermissions(@PathVariable Long id, @Valid @RequestBody PermissionsRequest r) {
        return roles.setPermissions(id, r.permissionNames());
    }
}
