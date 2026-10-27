package vn.webdoc.lite.web;

import java.util.List;

import org.springframework.http.HttpStatus;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import vn.webdoc.lite.service.CurrentUser;
import vn.webdoc.lite.service.OrganizationService;
import vn.webdoc.lite.web.Dtos.DepartmentRequest;
import vn.webdoc.lite.web.Dtos.DepartmentResponse;
import vn.webdoc.lite.web.Dtos.OrganizationRequest;
import vn.webdoc.lite.web.Dtos.OrganizationResponse;

@RestController
@RequestMapping("/api/v1")
@RequiredArgsConstructor
public class OrganizationController {
    private static final String ADMIN = "hasRole('SYSTEM_ADMIN')";

    private final OrganizationService orgs;

    @GetMapping("/organizations")
    public List<OrganizationResponse> organizations() {
        return orgs.listOrganizations(CurrentUser.username());
    }

    @GetMapping("/organizations/{id}")
    public OrganizationResponse organization(@PathVariable Long id) {
        return orgs.getOrganization(CurrentUser.username(), id);
    }

    @PostMapping("/organizations")
    @PreAuthorize(ADMIN)
    @ResponseStatus(HttpStatus.CREATED)
    public OrganizationResponse createOrganization(@Valid @RequestBody OrganizationRequest r) {
        return orgs.createOrganization(r);
    }

    @PutMapping("/organizations/{id}")
    @PreAuthorize(ADMIN)
    public OrganizationResponse updateOrganization(@PathVariable Long id, @Valid @RequestBody OrganizationRequest r) {
        return orgs.updateOrganization(id, r);
    }

    @GetMapping("/departments/organization/{organizationId}")
    public List<DepartmentResponse> departments(@PathVariable Long organizationId) {
        return orgs.listDepartments(CurrentUser.username(), organizationId);
    }

    @PostMapping("/departments")
    @ResponseStatus(HttpStatus.CREATED)
    public DepartmentResponse createDepartment(@Valid @RequestBody DepartmentRequest r) {
        return orgs.createDepartment(CurrentUser.username(), r);
    }

    @PutMapping("/departments/{id}")
    public DepartmentResponse updateDepartment(@PathVariable Long id, @Valid @RequestBody DepartmentRequest r) {
        return orgs.updateDepartment(CurrentUser.username(), id, r);
    }

    @DeleteMapping("/departments/{id}")
    public void deleteDepartment(@PathVariable Long id) {
        orgs.deleteDepartment(CurrentUser.username(), id);
    }
}
