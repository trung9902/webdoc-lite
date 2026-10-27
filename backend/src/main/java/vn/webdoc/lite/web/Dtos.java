package vn.webdoc.lite.web;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Set;

import com.fasterxml.jackson.annotation.JsonAlias;
import com.fasterxml.jackson.annotation.JsonProperty;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

/** Các kiểu dữ liệu vào/ra của API. Tên trường JSON đặt theo camelCase, riêng token theo snake_case như WebDoc thật. */
public final class Dtos {
    private Dtos() {
    }

    /** Trường email nhận cả tên đăng nhập lẫn email, giống WebDoc thật. */
    public record LoginRequest(@NotBlank String email, @NotBlank String password) {
    }

    public record RefreshRequest(@JsonProperty("refresh_token") @JsonAlias("refreshToken") @NotBlank String refreshToken) {
    }

    public record TokenResponse(@JsonProperty("access_token") String accessToken,
            @JsonProperty("refresh_token") String refreshToken) {
    }

    public record ProfileResponse(Long id, String username, String email, String firstName, String lastName,
            String fullName, Boolean gender, int status, boolean admin, boolean organizationManager,
            boolean deptManager, Long organizationId, String organizationName, Long deptId, String departmentName,
            Set<String> roleNames, Set<String> roleCodes, Set<String> permissionNames, Set<String> areas,
            boolean mfa, LocalDateTime createdAt) {
    }

    public record UpdateProfileRequest(@NotBlank @Size(max = 30, message = "Tên tối đa 30 ký tự") String firstName,
            @NotBlank @Size(max = 30, message = "Họ và tên đệm tối đa 30 ký tự") String lastName, Boolean gender) {
    }

    /** Dùng cho tạo và sửa người dùng; trường null nghĩa là giữ nguyên khi sửa. */
    public record UserUpsertRequest(String username, String email, String password, String firstName,
            String lastName, Boolean gender, Long organizationId, Long departmentId, Set<String> roleCodes,
            Set<String> areas, Boolean mfaEnabled, Boolean organizationManager, Boolean deptManager) {
    }

    public record UserPage(List<ProfileResponse> list, long total, int page, int size) {
    }

    public record StatusRequest(@NotNull Long userId, @NotNull @Min(1) @Max(2) Integer status) {
    }

    /** Chấp nhận cả "admin" lẫn "isAdmin" để khớp giao diện WebDoc thật. */
    public record RoleChangeRequest(@NotNull Long userId, @NotNull @JsonAlias({ "admin" }) Boolean isAdmin) {
    }

    public record PermissionsRequest(@NotNull Set<String> permissionNames) {
    }

    public record RoleResponse(Long id, String code, String name, String description, Set<String> permissionNames) {
    }

    public record PermissionResponse(Long id, String name, String description, String groupName) {
    }

    public record OrganizationRequest(@NotBlank String code, @NotBlank String name, String description) {
    }

    public record OrganizationResponse(Long id, String code, String name, String description, int status) {
    }

    public record DepartmentRequest(@NotBlank String name, String description, Long organizationId) {
    }

    public record DepartmentResponse(Long id, Long organizationId, String name, String description, int status) {
    }

    public record DocumentResponse(Long id, String title, String originalFilename, String type, long sizeBytes,
            double sizeKb, int pageCount, String status, String accessLevel, String area, Long departmentId,
            String departmentName, String createdBy, LocalDateTime createdAt, String contentHash,
            String description) {
    }

    public record DocumentDetail(DocumentResponse info, List<String> pages) {
    }

    public record DocumentPage(List<DocumentResponse> list, long total, int page, int size) {
    }
}
