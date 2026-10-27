package vn.webdoc.lite.service;

import org.springframework.http.HttpStatus;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import lombok.RequiredArgsConstructor;
import vn.webdoc.lite.config.ApiException;
import vn.webdoc.lite.config.JwtService;
import vn.webdoc.lite.domain.UserAccount;
import vn.webdoc.lite.repo.UserRepository;
import vn.webdoc.lite.web.Dtos.TokenResponse;

@Service
@RequiredArgsConstructor
public class AuthService {
    private final UserRepository users;
    private final PasswordEncoder encoder;
    private final JwtService jwt;

    @Transactional(readOnly = true)
    public TokenResponse login(String identifier, String password) {
        UserAccount user = users.findByUsernameIgnoreCase(identifier.trim())
                .or(() -> users.findByEmailIgnoreCase(identifier.trim()))
                .orElse(null);
        // Luôn so khớp mật khẩu (kể cả khi không có tài khoản) để thời gian phản hồi không lộ tài khoản có tồn tại hay không.
        String hash = user != null ? user.getPasswordHash() : "$2a$10$7EqJtq98hPqEX7fNZaFWoOhi5BUy6M9bUC7cUGg0r3ZyPPgm1q0ya";
        boolean ok = encoder.matches(password, hash);
        if (user == null || !ok) {
            throw new ApiException(HttpStatus.UNAUTHORIZED, "bad_credentials", "Sai tên đăng nhập hoặc mật khẩu.");
        }
        if (user.getStatus() != 1) {
            throw new ApiException(HttpStatus.FORBIDDEN, "account_locked", "Tài khoản đã bị khoá.");
        }
        return tokens(user);
    }

    @Transactional(readOnly = true)
    public TokenResponse refresh(String refreshToken) {
        Jwt parsed;
        try {
            parsed = jwt.parse(refreshToken);
        } catch (JwtException e) {
            throw new ApiException(HttpStatus.UNAUTHORIZED, "invalid_token", "Phiên đăng nhập đã hết hạn.");
        }
        if (!JwtService.REFRESH.equals(parsed.getClaimAsString("typ"))) {
            throw new ApiException(HttpStatus.UNAUTHORIZED, "invalid_token", "Token không hợp lệ.");
        }
        UserAccount user = users.findByUsernameIgnoreCase(parsed.getSubject())
                .filter(u -> u.getStatus() == 1)
                .orElseThrow(() -> new ApiException(HttpStatus.UNAUTHORIZED, "invalid_token", "Tài khoản không hợp lệ."));
        return tokens(user);
    }

    private TokenResponse tokens(UserAccount user) {
        return new TokenResponse(jwt.accessToken(user.getUsername(), user.getId()),
                jwt.refreshToken(user.getUsername(), user.getId()));
    }
}
