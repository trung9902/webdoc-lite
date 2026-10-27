package vn.webdoc.lite.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Entity
@Table(name = "permissions")
@Getter
@Setter
@NoArgsConstructor
public class Permission {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    /** Tên quyền, ví dụ gaa.search. */
    @Column(nullable = false, unique = true)
    private String name;

    private String description;

    /** Nhóm quyền hiển thị trên màn hình phân quyền, ví dụ "Phân hệ Agent". */
    private String groupName;
}
