package vn.webdoc.lite.domain;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

import jakarta.persistence.CollectionTable;
import jakarta.persistence.Column;
import jakarta.persistence.ElementCollection;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.OrderColumn;
import jakarta.persistence.Table;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Entity
@Table(name = "documents")
@Getter
@Setter
@NoArgsConstructor
public class DocumentRecord {
    public static final String PUBLISHED = "PUBLISHED";
    public static final String DRAFT = "DRAFT";
    public static final String PUBLIC = "PUBLIC";
    public static final String INTERNAL = "INTERNAL";
    public static final String PRIVATE = "PRIVATE";

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false)
    private String title;

    private String originalFilename;

    /** Định dạng tệp: pdf, png, docx, xlsx... */
    private String type;

    private long sizeBytes;

    private int pageCount;

    /** DRAFT hoặc PUBLISHED. */
    private String status = PUBLISHED;

    /** PUBLIC, INTERNAL hoặc PRIVATE (chỉ người tạo xem được). */
    private String accessLevel = INTERNAL;

    /** Phường mà tài liệu thuộc về; rỗng nghĩa là không gắn phường. */
    private String area;

    private String description;

    /** SHA-256 của nội dung chữ; dùng nhận biết bản trùng. */
    private String contentHash;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "organization_id")
    private Organization organization;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "department_id")
    private Department department;

    /** Tên đăng nhập người tạo. */
    @Column(nullable = false)
    private String createdBy;

    private LocalDateTime createdAt = LocalDateTime.now();

    /** Chữ nhận dạng (OCR) theo từng trang, trang 1 là phần tử đầu tiên. */
    @ElementCollection(fetch = FetchType.LAZY)
    @CollectionTable(name = "document_pages", joinColumns = @JoinColumn(name = "document_id"))
    @OrderColumn(name = "page_index")
    @Column(name = "page_text", length = 20000)
    private List<String> pages = new ArrayList<>();
}
