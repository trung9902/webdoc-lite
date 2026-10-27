package vn.webdoc.lite.service;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import jakarta.persistence.criteria.Predicate;
import lombok.RequiredArgsConstructor;
import vn.webdoc.lite.config.ApiException;
import vn.webdoc.lite.domain.Department;
import vn.webdoc.lite.domain.Organization;
import vn.webdoc.lite.domain.Permission;
import vn.webdoc.lite.domain.Role;
import vn.webdoc.lite.domain.UserAccount;
import vn.webdoc.lite.repo.DepartmentRepository;
import vn.webdoc.lite.repo.OrganizationRepository;
import vn.webdoc.lite.repo.PermissionRepository;
import vn.webdoc.lite.repo.RoleRepository;
import vn.webdoc.lite.repo.UserRepository;
import vn.webdoc.lite.web.Dtos.ProfileResponse;
import vn.webdoc.lite.web.Dtos.UpdateProfileRequest;
import vn.webdoc.lite.web.Dtos.UserPage;
import vn.webdoc.lite.web.Dtos.UserUpsertRequest;

@Service
@RequiredArgsConstructor
@Transactional
public class UserService {
    private final UserRepository users;
    private final RoleRepository roles;
    private final PermissionRepository permissions;
    private final OrganizationRepository organizations;
    private final DepartmentRepository departments;
    private final PermissionService permissionService;
    private final PasswordEncoder encoder;

    // ---------- đọc ----------

    @Transactional(readOnly = true)
    public UserAccount byUsername(String username) {
        return users.findByUsernameIgnoreCase(username)
                .orElseThrow(() -> ApiException.notFound("Không tìm thấy người dùng."));
    }

    @Transactional(readOnly = true)
    public ProfileResponse profile(String username) {
        return toProfile(byUsername(username));
    }

    @Transactional(readOnly = true)
    public ProfileResponse get(String actorUsername, Long id) {
        UserAccount actor = byUsername(actorUsername);
        UserAccount target = users.findById(id).orElseThrow(() -> ApiException.notFound("Không tìm thấy người dùng."));
        boolean self = actor.getId().equals(target.getId());
        boolean sameOrg = actor.getOrganization() != null && target.getOrganization() != null
                && actor.getOrganization().getId().equals(target.getOrganization().getId());
        if (!(actor.isAdmin() || self || sameOrg)) {
            throw ApiException.forbidden("Bạn không được xem người dùng này.");
        }
        return toProfile(target);
    }

    /** Quản trị xem mọi tổ chức; người khác chỉ thấy người cùng tổ chức. */
    @Transactional(readOnly = true)
    public UserPage filter(String actorUsername, String q, Long organizationId, int page, int size) {
        UserAccount actor = byUsername(actorUsername);
        Long orgScope = actor.isAdmin() ? organizationId
                : actor.getOrganization() == null ? Long.valueOf(-1) : actor.getOrganization().getId();
        Specification<UserAccount> spec = (root, query, cb) -> {
            List<Predicate> and = new ArrayList<>();
            if (orgScope != null) {
                and.add(cb.equal(root.get("organization").get("id"), orgScope));
            }
            if (q != null && !q.isBlank()) {
                String like = "%" + q.trim().toLowerCase() + "%";
                and.add(cb.or(cb.like(cb.lower(root.get("username")), like), cb.like(cb.lower(root.get("email")), like),
                        cb.like(cb.lower(root.get("firstName")), like), cb.like(cb.lower(root.get("lastName")), like)));
            }
            return cb.and(and.toArray(new Predicate[0]));
        };
        Page<UserAccount> result = users.findAll(spec,
                PageRequest.of(Math.max(page, 0), Math.min(Math.max(size, 1), 100), Sort.by("id")));
        return new UserPage(result.getContent().stream().map(this::toProfile).toList(), result.getTotalElements(),
                result.getNumber(), result.getSize());
    }

    // ---------- ghi ----------

    public ProfileResponse updateProfile(String username, UpdateProfileRequest r) {
        UserAccount u = byUsername(username);
        u.setFirstName(normalize(r.firstName()));
        u.setLastName(normalize(r.lastName()));
        if (r.gender() != null) {
            u.setGender(r.gender());
        }
        return toProfile(users.save(u));
    }

    public ProfileResponse create(UserUpsertRequest r) {
        if (blank(r.username()) || blank(r.password()) || blank(r.email())) {
            throw ApiException.badRequest("Cần có tên đăng nhập, email và mật khẩu.");
        }
        if (r.password().length() < 8) {
            throw ApiException.badRequest("Mật khẩu tối thiểu 8 ký tự.");
        }
        if (users.existsByUsernameIgnoreCase(r.username().trim())) {
            throw ApiException.badRequest("Tên đăng nhập đã tồn tại.");
        }
        UserAccount u = new UserAccount();
        u.setUsername(r.username().trim());
        u.setPasswordHash(encoder.encode(r.password()));
        apply(u, r);
        return toProfile(users.save(u));
    }

    public ProfileResponse update(Long id, UserUpsertRequest r) {
        UserAccount u = users.findById(id).orElseThrow(() -> ApiException.notFound("Không tìm thấy người dùng."));
        if (!blank(r.password())) {
            if (r.password().length() < 8) {
                throw ApiException.badRequest("Mật khẩu tối thiểu 8 ký tự.");
            }
            u.setPasswordHash(encoder.encode(r.password()));
        }
        apply(u, r);
        return toProfile(users.save(u));
    }

    public void setStatus(String actorUsername, Long userId, int status) {
        UserAccount u = users.findById(userId).orElseThrow(() -> ApiException.notFound("Không tìm thấy người dùng."));
        if (u.getUsername().equalsIgnoreCase(actorUsername) && status != 1) {
            throw ApiException.badRequest("Không thể tự khoá tài khoản của chính mình.");
        }
        u.setStatus(status);
        users.save(u);
    }

    public void setAdmin(String actorUsername, Long userId, boolean admin) {
        UserAccount u = users.findById(userId).orElseThrow(() -> ApiException.notFound("Không tìm thấy người dùng."));
        if (u.getUsername().equalsIgnoreCase(actorUsername) && !admin) {
            throw ApiException.badRequest("Không thể tự gỡ quyền quản trị của chính mình.");
        }
        u.setAdmin(admin);
        users.save(u);
    }

    public ProfileResponse setExtraPermissions(Long userId, Set<String> names) {
        UserAccount u = users.findById(userId).orElseThrow(() -> ApiException.notFound("Không tìm thấy người dùng."));
        u.setExtraPermissions(resolvePermissions(names));
        return toProfile(users.save(u));
    }

    // ---------- nội bộ ----------

    private void apply(UserAccount u, UserUpsertRequest r) {
        if (r.email() != null) {
            u.setEmail(r.email().trim());
        }
        if (r.firstName() != null) {
            u.setFirstName(normalize(r.firstName()));
        }
        if (r.lastName() != null) {
            u.setLastName(normalize(r.lastName()));
        }
        if (r.gender() != null) {
            u.setGender(r.gender());
        }
        if (r.mfaEnabled() != null) {
            u.setMfaEnabled(r.mfaEnabled());
        }
        if (r.organizationManager() != null) {
            u.setOrganizationManager(r.organizationManager());
        }
        if (r.deptManager() != null) {
            u.setDeptManager(r.deptManager());
        }
        if (r.organizationId() != null) {
            Organization org = organizations.findById(r.organizationId())
                    .orElseThrow(() -> ApiException.badRequest("Tổ chức không tồn tại."));
            u.setOrganization(org);
        }
        if (r.departmentId() != null) {
            Department d = departments.findById(r.departmentId())
                    .orElseThrow(() -> ApiException.badRequest("Phòng ban không tồn tại."));
            if (u.getOrganization() == null || !d.getOrganization().getId().equals(u.getOrganization().getId())) {
                throw ApiException.badRequest("Phòng ban không thuộc tổ chức của người dùng.");
            }
            u.setDepartment(d);
        }
        if (r.roleCodes() != null) {
            List<Role> found = roles.findByCodeIn(r.roleCodes());
            if (found.size() != r.roleCodes().size()) {
                throw ApiException.badRequest("Có vai trò không tồn tại.");
            }
            u.setRoles(new LinkedHashSet<>(found));
        }
        if (r.areas() != null) {
            u.setAreas(r.areas().stream().filter(a -> !blank(a)).map(String::trim)
                    .collect(Collectors.toCollection(LinkedHashSet::new)));
        }
        if (u.getEmail() == null) {
            throw ApiException.badRequest("Cần có email.");
        }
    }

    private Set<Permission> resolvePermissions(Set<String> names) {
        List<Permission> found = permissions.findByNameIn(names);
        if (found.size() != names.size()) {
            throw ApiException.badRequest("Có quyền không tồn tại.");
        }
        return new LinkedHashSet<>(found);
    }

    public ProfileResponse toProfile(UserAccount u) {
        Set<String> perms = permissionService.effective(u);
        return new ProfileResponse(u.getId(), u.getUsername(), u.getEmail(), u.getFirstName(), u.getLastName(),
                u.fullName(), u.getGender(), u.getStatus(), u.isAdmin(), u.isOrganizationManager(), u.isDeptManager(),
                u.getOrganization() == null ? null : u.getOrganization().getId(),
                u.getOrganization() == null ? null : u.getOrganization().getName(),
                u.getDepartment() == null ? null : u.getDepartment().getId(),
                u.getDepartment() == null ? null : u.getDepartment().getName(),
                u.getRoles().stream().map(Role::getName).collect(Collectors.toCollection(LinkedHashSet::new)),
                u.getRoles().stream().map(Role::getCode).collect(Collectors.toCollection(LinkedHashSet::new)),
                perms, new LinkedHashSet<>(u.getAreas()), u.isMfaEnabled(), u.getCreatedAt());
    }

    private static boolean blank(String s) {
        return s == null || s.isBlank();
    }

    /** Cắt khoảng trắng đầu cuối và gộp khoảng trắng thừa ở giữa. */
    private static String normalize(String s) {
        return s == null ? null : s.trim().replaceAll("\\s+", " ");
    }
}
