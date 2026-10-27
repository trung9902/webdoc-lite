package vn.webdoc.lite.service;

import java.util.Comparator;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import java.util.TreeSet;
import java.util.stream.Collectors;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import lombok.RequiredArgsConstructor;
import vn.webdoc.lite.config.ApiException;
import vn.webdoc.lite.domain.Permission;
import vn.webdoc.lite.domain.Role;
import vn.webdoc.lite.repo.PermissionRepository;
import vn.webdoc.lite.repo.RoleRepository;
import vn.webdoc.lite.web.Dtos.PermissionResponse;
import vn.webdoc.lite.web.Dtos.RoleResponse;

@Service
@RequiredArgsConstructor
@Transactional
public class RoleService {
    private final RoleRepository roles;
    private final PermissionRepository permissions;

    @Transactional(readOnly = true)
    public List<RoleResponse> listRoles() {
        return roles.findAll().stream().sorted(Comparator.comparing(Role::getId)).map(RoleService::toDto).toList();
    }

    @Transactional(readOnly = true)
    public List<PermissionResponse> listPermissions() {
        return permissions.findAll().stream()
                .sorted(Comparator.comparing(Permission::getGroupName, Comparator.nullsLast(String::compareTo))
                        .thenComparing(Permission::getName))
                .map(p -> new PermissionResponse(p.getId(), p.getName(), p.getDescription(), p.getGroupName()))
                .toList();
    }

    /** Thay toàn bộ quyền của một vai trò (ma trận quyền theo vai trò). */
    public RoleResponse setPermissions(Long roleId, Set<String> names) {
        Role role = roles.findById(roleId).orElseThrow(() -> ApiException.notFound("Không tìm thấy vai trò."));
        List<Permission> found = permissions.findByNameIn(names);
        if (found.size() != names.size()) {
            throw ApiException.badRequest("Có quyền không tồn tại.");
        }
        role.setPermissions(new LinkedHashSet<>(found));
        return toDto(roles.save(role));
    }

    private static RoleResponse toDto(Role r) {
        Set<String> names = r.getPermissions().stream().map(Permission::getName)
                .collect(Collectors.toCollection(TreeSet::new));
        return new RoleResponse(r.getId(), r.getCode(), r.getName(), r.getDescription(), names);
    }
}
