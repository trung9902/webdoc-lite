package vn.webdoc.lite.web;

import java.time.LocalDate;

import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import lombok.RequiredArgsConstructor;
import vn.webdoc.lite.service.CurrentUser;
import vn.webdoc.lite.service.DocumentService;
import vn.webdoc.lite.service.DocumentService.Filter;
import vn.webdoc.lite.web.Dtos.DocumentDetail;
import vn.webdoc.lite.web.Dtos.DocumentPage;

@RestController
@RequestMapping("/api/v1/documents")
@RequiredArgsConstructor
public class DocumentController {
    private final DocumentService documents;

    /**
     * Danh sách tài liệu theo phạm vi xem của người đang đăng nhập.
     * maxSizeKb là cận trên LOẠI TRỪ: maxSizeKb=100 nghĩa là "dưới 100 KB" (tệp đúng 100 KB không tính).
     */
    @GetMapping("/filter")
    public DocumentPage filter(@RequestParam(required = false) String q,
            @RequestParam(required = false) String text,
            @RequestParam(required = false) String type,
            @RequestParam(required = false) String area,
            @RequestParam(required = false) Long departmentId,
            @RequestParam(required = false) Double minSizeKb,
            @RequestParam(required = false) Double maxSizeKb,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate from,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate to,
            @RequestParam(defaultValue = "0") int page, @RequestParam(defaultValue = "20") int size) {
        Filter f = new Filter(q, text, type, area, departmentId, minSizeKb, maxSizeKb, from, to);
        return documents.search(CurrentUser.username(), f, page, size);
    }

    @GetMapping("/{id}")
    public DocumentDetail get(@PathVariable Long id) {
        return documents.get(CurrentUser.username(), id);
    }
}
