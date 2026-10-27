package vn.webdoc.lite.service;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import jakarta.persistence.criteria.JoinType;
import jakarta.persistence.criteria.Predicate;
import lombok.RequiredArgsConstructor;
import vn.webdoc.lite.config.ApiException;
import vn.webdoc.lite.domain.DocumentRecord;
import vn.webdoc.lite.domain.UserAccount;
import vn.webdoc.lite.repo.DocumentRepository;
import vn.webdoc.lite.web.Dtos.DocumentDetail;
import vn.webdoc.lite.web.Dtos.DocumentPage;
import vn.webdoc.lite.web.Dtos.DocumentResponse;

/**
 * Tìm và đọc tài liệu có áp phạm vi xem của người dùng ("lọc lần 1" của WebDoc).
 * Phân hệ mới cần danh sách tài liệu thì gọi {@link #search}, không tự truy vấn bảng documents.
 */
@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class DocumentService {
    private static final double KB = 1024.0;

    private final DocumentRepository documents;
    private final UserService userService;

    /** Bộ lọc tìm kiếm. Trường null nghĩa là không lọc theo trường đó. */
    public record Filter(String q, String text, String type, String area, Long departmentId, Double minSizeKb,
            Double maxSizeKbExclusive, LocalDate from, LocalDate to) {
    }

    public DocumentPage search(String viewerUsername, Filter f, int page, int size) {
        UserAccount viewer = userService.byUsername(viewerUsername);
        Page<DocumentRecord> result = documents.findAll(visibleTo(viewer).and(matching(f)),
                PageRequest.of(Math.max(page, 0), Math.min(Math.max(size, 1), 200),
                        Sort.by(Sort.Direction.DESC, "createdAt").and(Sort.by("id"))));
        return new DocumentPage(result.getContent().stream().map(DocumentService::toDto).toList(),
                result.getTotalElements(), result.getNumber(), result.getSize());
    }

    public DocumentDetail get(String viewerUsername, Long id) {
        UserAccount viewer = userService.byUsername(viewerUsername);
        DocumentRecord d = documents.findOne(visibleTo(viewer).and((root, q, cb) -> cb.equal(root.get("id"), id)))
                .orElseThrow(() -> ApiException.notFound("Không tìm thấy tài liệu hoặc bạn không có quyền xem."));
        return new DocumentDetail(toDto(d), List.copyOf(d.getPages()));
    }

    /**
     * Quy tắc xem:
     * - chỉ tài liệu cùng tổ chức;
     * - nếu người dùng có thuộc tính phường thì chỉ thấy tài liệu thuộc các phường đó;
     * - tài liệu của chính mình luôn thấy; tài liệu PRIVATE của người khác thì không;
     * - bản nháp chỉ người tạo, quản trị viên và quản lý tổ chức thấy.
     */
    static Specification<DocumentRecord> visibleTo(UserAccount viewer) {
        return (root, query, cb) -> {
            if (viewer.getOrganization() == null) {
                return cb.disjunction();
            }
            List<Predicate> and = new ArrayList<>();
            and.add(cb.equal(root.get("organization").get("id"), viewer.getOrganization().getId()));
            if (!viewer.getAreas().isEmpty()) {
                and.add(root.get("area").in(viewer.getAreas()));
            }
            Predicate own = cb.equal(root.get("createdBy"), viewer.getUsername());
            Predicate published = cb.equal(root.get("status"), DocumentRecord.PUBLISHED);
            Predicate draftOk = (viewer.isAdmin() || viewer.isOrganizationManager()) ? cb.conjunction() : published;
            Predicate shared = cb.and(cb.notEqual(root.get("accessLevel"), DocumentRecord.PRIVATE), draftOk);
            and.add(cb.or(own, shared));
            return cb.and(and.toArray(new Predicate[0]));
        };
    }

    private static Specification<DocumentRecord> matching(Filter f) {
        return (root, query, cb) -> {
            List<Predicate> and = new ArrayList<>();
            if (notBlank(f.q())) {
                String like = "%" + f.q().trim().toLowerCase() + "%";
                and.add(cb.or(cb.like(cb.lower(root.get("title")), like),
                        cb.like(cb.lower(root.get("originalFilename")), like)));
            }
            if (notBlank(f.text())) {
                query.distinct(true);
                and.add(cb.like(cb.lower(root.join("pages", JoinType.LEFT)), "%" + f.text().trim().toLowerCase() + "%"));
            }
            if (notBlank(f.type())) {
                and.add(cb.equal(cb.lower(root.get("type")), f.type().trim().toLowerCase()));
            }
            if (notBlank(f.area())) {
                and.add(cb.equal(root.get("area"), f.area().trim()));
            }
            if (f.departmentId() != null) {
                and.add(cb.equal(root.get("department").get("id"), f.departmentId()));
            }
            if (f.minSizeKb() != null) {
                and.add(cb.greaterThanOrEqualTo(root.get("sizeBytes"), (long) Math.ceil(f.minSizeKb() * KB)));
            }
            if (f.maxSizeKbExclusive() != null) {
                and.add(cb.lessThan(root.get("sizeBytes"), (long) Math.ceil(f.maxSizeKbExclusive() * KB)));
            }
            if (f.from() != null) {
                and.add(cb.greaterThanOrEqualTo(root.get("createdAt"), f.from().atStartOfDay()));
            }
            if (f.to() != null) {
                and.add(cb.lessThan(root.get("createdAt"), f.to().plusDays(1).atStartOfDay()));
            }
            return cb.and(and.toArray(new Predicate[0]));
        };
    }

    private static boolean notBlank(String s) {
        return s != null && !s.isBlank();
    }

    static DocumentResponse toDto(DocumentRecord d) {
        return new DocumentResponse(d.getId(), d.getTitle(), d.getOriginalFilename(), d.getType(), d.getSizeBytes(),
                Math.round(d.getSizeBytes() / KB * 10.0) / 10.0, d.getPageCount(), d.getStatus(), d.getAccessLevel(),
                d.getArea(), d.getDepartment() == null ? null : d.getDepartment().getId(),
                d.getDepartment() == null ? null : d.getDepartment().getName(), d.getCreatedBy(), d.getCreatedAt(),
                d.getContentHash(), d.getDescription());
    }
}
