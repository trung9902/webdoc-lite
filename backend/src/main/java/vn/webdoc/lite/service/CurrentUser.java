package vn.webdoc.lite.service;

import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;

import vn.webdoc.lite.config.ApiException;

/** Lấy tên đăng nhập của người đang gọi API từ ngữ cảnh bảo mật (không bao giờ nhận từ tham số yêu cầu). */
public final class CurrentUser {
    private CurrentUser() {
    }

    public static String username() {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth == null || !auth.isAuthenticated() || "anonymousUser".equals(auth.getName())) {
            throw new ApiException(org.springframework.http.HttpStatus.UNAUTHORIZED, "unauthenticated",
                    "Chưa đăng nhập.");
        }
        return auth.getName();
    }
}
