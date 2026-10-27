package vn.webdoc.lite.web;

import org.springframework.http.HttpStatus;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import vn.webdoc.lite.service.CurrentUser;
import vn.webdoc.lite.service.UserService;
import vn.webdoc.lite.web.Dtos.PermissionsRequest;
import vn.webdoc.lite.web.Dtos.ProfileResponse;
import vn.webdoc.lite.web.Dtos.RoleChangeRequest;
import vn.webdoc.lite.web.Dtos.StatusRequest;
import vn.webdoc.lite.web.Dtos.UpdateProfileRequest;
import vn.webdoc.lite.web.Dtos.UserPage;
import vn.webdoc.lite.web.Dtos.UserUpsertRequest;

@RestController
@RequestMapping("/api/v1/users")
@RequiredArgsConstructor
public class UserController {
    private static final String ADMIN = "hasRole('SYSTEM_ADMIN')";

    private final UserService users;

    @GetMapping("/profile")
    public ProfileResponse profile() {
        return users.profile(CurrentUser.username());
    }

    @PutMapping("/profile")
    public ProfileResponse updateProfile(@Valid @RequestBody UpdateProfileRequest r) {
        return users.updateProfile(CurrentUser.username(), r);
    }

    @GetMapping("/filter")
    public UserPage filter(@RequestParam(required = false) String q,
            @RequestParam(required = false) Long organizationId,
            @RequestParam(defaultValue = "0") int page, @RequestParam(defaultValue = "10") int size) {
        return users.filter(CurrentUser.username(), q, organizationId, page, size);
    }

    @GetMapping("/{id}")
    public ProfileResponse get(@PathVariable Long id) {
        return users.get(CurrentUser.username(), id);
    }

    @PostMapping
    @PreAuthorize(ADMIN)
    @ResponseStatus(HttpStatus.CREATED)
    public ProfileResponse create(@RequestBody UserUpsertRequest r) {
        return users.create(r);
    }

    @PutMapping("/{id}")
    @PreAuthorize(ADMIN)
    public ProfileResponse update(@PathVariable Long id, @RequestBody UserUpsertRequest r) {
        return users.update(id, r);
    }

    @PutMapping("/status")
    @PreAuthorize(ADMIN)
    public void status(@Valid @RequestBody StatusRequest r) {
        users.setStatus(CurrentUser.username(), r.userId(), r.status());
    }

    @PutMapping("/role")
    @PreAuthorize(ADMIN)
    public void role(@Valid @RequestBody RoleChangeRequest r) {
        users.setAdmin(CurrentUser.username(), r.userId(), r.isAdmin());
    }

    /** Quyền bổ sung riêng cho một người dùng (cộng thêm vào quyền của vai trò). */
    @PutMapping("/{id}/permissions")
    @PreAuthorize(ADMIN)
    public ProfileResponse extraPermissions(@PathVariable Long id, @Valid @RequestBody PermissionsRequest r) {
        return users.setExtraPermissions(id, r.permissionNames());
    }
}
