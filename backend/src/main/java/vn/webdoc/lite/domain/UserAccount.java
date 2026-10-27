package vn.webdoc.lite.domain;

import java.time.LocalDateTime;
import java.util.LinkedHashSet;
import java.util.Set;

import jakarta.persistence.CollectionTable;
import jakarta.persistence.Column;
import jakarta.persistence.ElementCollection;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.JoinTable;
import jakarta.persistence.ManyToMany;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Entity
@Table(name = "users")
@Getter
@Setter
@NoArgsConstructor
public class UserAccount {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, unique = true)
    private String username;

    @Column(nullable = false)
    private String email;

    @Column(nullable = false)
    private String passwordHash;

    /** Tên. */
    private String firstName;

    /** Họ và tên đệm. */
    private String lastName;

    private Boolean gender;

    /** 1 = hoạt động, 2 = bị khoá. */
    private int status = 1;

    private boolean admin;

    private boolean organizationManager;

    private boolean deptManager;

    /** Mô phỏng đã xác thực 2 lớp (MFA). Quyền nhạy cảm chỉ có ý nghĩa khi bật. */
    private boolean mfaEnabled;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "organization_id")
    private Organization organization;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "department_id")
    private Department department;

    @ManyToMany(fetch = FetchType.LAZY)
    @JoinTable(name = "user_roles",
            joinColumns = @JoinColumn(name = "user_id"),
            inverseJoinColumns = @JoinColumn(name = "role_id"))
    private Set<Role> roles = new LinkedHashSet<>();

    /** Quyền bổ sung riêng cho người dùng, cộng thêm vào quyền của vai trò. */
    @ManyToMany(fetch = FetchType.LAZY)
    @JoinTable(name = "user_permissions",
            joinColumns = @JoinColumn(name = "user_id"),
            inverseJoinColumns = @JoinColumn(name = "permission_id"))
    private Set<Permission> extraPermissions = new LinkedHashSet<>();

    /** Thuộc tính ABAC: các phường người dùng được xem. Rỗng nghĩa là không giới hạn phường. */
    @ElementCollection(fetch = FetchType.EAGER)
    @CollectionTable(name = "user_areas", joinColumns = @JoinColumn(name = "user_id"))
    @Column(name = "area")
    private Set<String> areas = new LinkedHashSet<>();

    private LocalDateTime createdAt = LocalDateTime.now();

    public String fullName() {
        return ((lastName == null ? "" : lastName) + " " + (firstName == null ? "" : firstName)).trim();
    }
}
