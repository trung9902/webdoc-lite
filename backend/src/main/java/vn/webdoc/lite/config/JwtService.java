package vn.webdoc.lite.config;

import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;

import javax.crypto.SecretKey;
import javax.crypto.spec.SecretKeySpec;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.oauth2.jose.jws.MacAlgorithm;
import org.springframework.security.oauth2.jwt.JwsHeader;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtClaimsSet;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.JwtEncoder;
import org.springframework.security.oauth2.jwt.JwtEncoderParameters;
import org.springframework.security.oauth2.jwt.NimbusJwtDecoder;
import org.springframework.security.oauth2.jwt.NimbusJwtEncoder;
import org.springframework.stereotype.Service;

import com.nimbusds.jose.jwk.source.ImmutableSecret;

/** Ký và kiểm JWT HS256 của chính WebDoc (đăng nhập). Token không chứa quyền: quyền luôn đọc lại từ CSDL. */
@Service
public class JwtService {
    public static final String ACCESS = "access";
    public static final String REFRESH = "refresh";

    private final JwtEncoder encoder;
    private final JwtDecoder decoder;
    private final Duration accessTtl;
    private final Duration refreshTtl;

    public JwtService(@Value("${webdoc.jwt.secret}") String secret,
            @Value("${webdoc.jwt.access-minutes}") long accessMinutes,
            @Value("${webdoc.jwt.refresh-days}") long refreshDays) {
        byte[] bytes = secret.getBytes(StandardCharsets.UTF_8);
        if (bytes.length < 32) {
            throw new IllegalStateException("WEBDOC_JWT_SECRET phải dài ít nhất 32 ký tự");
        }
        SecretKey key = new SecretKeySpec(bytes, "HmacSHA256");
        this.encoder = new NimbusJwtEncoder(new ImmutableSecret<>(key));
        this.decoder = NimbusJwtDecoder.withSecretKey(key).macAlgorithm(MacAlgorithm.HS256).build();
        this.accessTtl = Duration.ofMinutes(accessMinutes);
        this.refreshTtl = Duration.ofDays(refreshDays);
    }

    public String accessToken(String username, Long userId) {
        return issue(username, userId, ACCESS, accessTtl);
    }

    public String refreshToken(String username, Long userId) {
        return issue(username, userId, REFRESH, refreshTtl);
    }

    public JwtDecoder decoder() {
        return decoder;
    }

    public Jwt parse(String token) {
        return decoder.decode(token);
    }

    private String issue(String username, Long userId, String type, Duration ttl) {
        Instant now = Instant.now();
        JwtClaimsSet claims = JwtClaimsSet.builder()
                .issuer("webdoc")
                .subject(username)
                .issuedAt(now)
                .expiresAt(now.plus(ttl))
                .claim("uid", userId)
                .claim("typ", type)
                .build();
        JwsHeader header = JwsHeader.with(MacAlgorithm.HS256).build();
        return encoder.encode(JwtEncoderParameters.from(header, claims)).getTokenValue();
    }
}
