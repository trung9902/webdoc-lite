package vn.webdoc.lite.service;

import java.util.List;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import lombok.RequiredArgsConstructor;
import vn.webdoc.lite.config.ApiException;
import vn.webdoc.lite.domain.Department;
import vn.webdoc.lite.domain.Organization;
import vn.webdoc.lite.domain.UserAccount;
import vn.webdoc.lite.repo.DepartmentRepository;
import vn.webdoc.lite.repo.OrganizationRepository;
import vn.webdoc.lite.web.Dtos.DepartmentRequest;
import vn.webdoc.lite.web.Dtos.DepartmentResponse;
import vn.webdoc.lite.web.Dtos.OrganizationRequest;
import vn.webdoc.lite.web.Dtos.OrganizationResponse;

@Service
@RequiredArgsConstructor
@Transactional
public class OrganizationService {
    private static final int ACTIVE = 1;
    private static final int DELETED = 2;

    private final OrganizationRepository organizations;
    private final DepartmentRepository departments;
    private final UserService userService;

    // ---------- tổ chức ----------

    @Transactional(readOnly = true)
    public List<OrganizationResponse> listOrganizations(String actorUsername) {
        UserAccount actor = userService.byUsername(actorUsername);
        if (actor.isAdmin()) {
            return organizations.findAll().stream().map(OrganizationService::toDto).toList();
        }
        return actor.getOrganization() == null ? List.of() : List.of(toDto(actor.getOrganization()));
    }

    @Transactional(readOnly = true)
    public OrganizationResponse getOrganization(String actorUsername, Long id) {
        UserAccount actor = userService.byUsername(actorUsername);
        if (!actor.isAdmin() && (actor.getOrganization() == null || !actor.getOrganization().getId().equals(id))) {
            throw ApiException.forbidden("Bạn không được xem tổ chức này.");
        }
        return toDto(organizations.findById(id).orElseThrow(() -> ApiException.notFound("Không tìm thấy tổ chức.")));
    }

    public OrganizationResponse createOrganization(OrganizationRequest r) {
        if (organizations.findByCode(r.code().trim()).isPresent()) {
            throw ApiException.badRequest("Mã tổ chức đã tồn tại.");
        }
        Organization o = new Organization();
        o.setCode(r.code().trim());
        o.setName(r.name().trim());
        o.setDescription(r.description());
        return toDto(organizations.save(o));
    }

    public OrganizationResponse updateOrganization(Long id, OrganizationRequest r) {
        Organization o = organizations.findById(id).orElseThrow(() -> ApiException.notFound("Không tìm thấy tổ chức."));
        o.setName(r.name().trim());
        o.setDescription(r.description());
        return toDto(organizations.save(o));
    }

    // ---------- phòng ban ----------

    @Transactional(readOnly = true)
    public List<DepartmentResponse> listDepartments(String actorUsername, Long organizationId) {
        UserAccount actor = userService.byUsername(actorUsername);
        requireMember(actor, organizationId);
        return departments.findByOrganizationIdAndStatusOrderByName(organizationId, ACTIVE).stream()
                .map(OrganizationService::toDto).toList();
    }

    public DepartmentResponse createDepartment(String actorUsername, DepartmentRequest r) {
        if (r.organizationId() == null) {
            throw ApiException.badRequest("Cần chọn tổ chức.");
        }
        UserAccount actor = userService.byUsername(actorUsername);
        requireManager(actor, r.organizationId());
        if (departments.existsByOrganizationIdAndNameIgnoreCaseAndStatus(r.organizationId(), r.name().trim(), ACTIVE)) {
            throw ApiException.badRequest("Phòng ban đã tồn tại.");
        }
        Department d = new Department();
        d.setOrganization(organizations.findById(r.organizationId())
                .orElseThrow(() -> ApiException.badRequest("Tổ chức không tồn tại.")));
        d.setName(r.name().trim());
        d.setDescription(r.description());
        return toDto(departments.save(d));
    }

    public DepartmentResponse updateDepartment(String actorUsername, Long id, DepartmentRequest r) {
        Department d = departments.findById(id).orElseThrow(() -> ApiException.notFound("Không tìm thấy phòng ban."));
        requireManager(userService.byUsername(actorUsername), d.getOrganization().getId());
        d.setName(r.name().trim());
        d.setDescription(r.description());
        return toDto(departments.save(d));
    }

    public void deleteDepartment(String actorUsername, Long id) {
        Department d = departments.findById(id).orElseThrow(() -> ApiException.notFound("Không tìm thấy phòng ban."));
        requireManager(userService.byUsername(actorUsername), d.getOrganization().getId());
        d.setStatus(DELETED);
        departments.save(d);
    }

    // ---------- kiểm tra quyền theo tổ chức ----------

    private static void requireMember(UserAccount actor, Long organizationId) {
        boolean member = actor.getOrganization() != null && actor.getOrganization().getId().equals(organizationId);
        if (!actor.isAdmin() && !member) {
            throw ApiException.forbidden("Bạn không thuộc tổ chức này.");
        }
    }

    /** Quản trị hệ thống, hoặc quản lý của đúng tổ chức đó. */
    private static void requireManager(UserAccount actor, Long organizationId) {
        boolean manager = actor.isOrganizationManager() && actor.getOrganization() != null
                && actor.getOrganization().getId().equals(organizationId);
        if (!actor.isAdmin() && !manager) {
            throw ApiException.forbidden("Chỉ quản trị viên hoặc quản lý tổ chức mới thực hiện được.");
        }
    }

    private static OrganizationResponse toDto(Organization o) {
        return new OrganizationResponse(o.getId(), o.getCode(), o.getName(), o.getDescription(), o.getStatus());
    }

    private static DepartmentResponse toDto(Department d) {
        return new DepartmentResponse(d.getId(), d.getOrganization().getId(), d.getName(), d.getDescription(),
                d.getStatus());
    }
}
