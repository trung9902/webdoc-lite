package vn.webdoc.lite.config;

import java.util.Arrays;
import java.util.Collection;
import java.util.List;

import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.security.authentication.BadCredentialsException;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.server.resource.authentication.AbstractOAuth2TokenAuthenticationToken;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.CorsConfigurationSource;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;

import vn.webdoc.lite.service.AuthorityService;

@Configuration
@EnableMethodSecurity
public class SecurityConfig {

    /**
     * Mặc định MỌI đường dẫn đều phải đăng nhập, trừ vài đường dẫn công khai dưới đây.
     * Thêm API mới (ví dụ /api/agent/** hay /api/webdoc/**) sẽ tự được bảo vệ, không cần sửa ở đây.
     */
    @Bean
    SecurityFilterChain filterChain(HttpSecurity http, JwtService jwtService, AuthorityService authorities,
            @Qualifier("corsConfigurationSource") CorsConfigurationSource cors) throws Exception {
        http.csrf(c -> c.disable())
                .cors(c -> c.configurationSource(cors))
                .sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
                .authorizeHttpRequests(a -> a
                        .requestMatchers(HttpMethod.OPTIONS, "/**").permitAll()
                        .requestMatchers("/api/v1/auth/login", "/api/v1/auth/refresh-token", "/api/v1/ping").permitAll()
                        .anyRequest().authenticated())
                .oauth2ResourceServer(o -> o.jwt(j -> j.decoder(jwtService.decoder())
                        .jwtAuthenticationConverter(jwt -> toAuthentication(jwt, authorities))));
        return http.build();
    }

    /** Quyền được đọc lại từ CSDL ở mỗi yêu cầu nên thu hồi quyền có hiệu lực ngay, không cần đăng nhập lại. */
    private AbstractOAuth2TokenAuthenticationToken<Jwt> toAuthentication(Jwt jwt, AuthorityService authorities) {
        if (!JwtService.ACCESS.equals(jwt.getClaimAsString("typ"))) {
            throw new BadCredentialsException("Token không hợp lệ");
        }
        Collection<GrantedAuthority> granted = authorities.authoritiesOf(jwt.getSubject());
        return new JwtAuthenticationToken(jwt, granted, jwt.getSubject());
    }

    @Bean
    PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder();
    }

    @Bean
    CorsConfigurationSource corsConfigurationSource(@Value("${webdoc.cors-origins}") String origins) {
        CorsConfiguration cfg = new CorsConfiguration();
        cfg.setAllowedOrigins(List.of(Arrays.stream(origins.split(",")).map(String::trim).toArray(String[]::new)));
        cfg.setAllowedMethods(List.of("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"));
        cfg.setAllowedHeaders(List.of("*"));
        cfg.setAllowCredentials(true);
        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/**", cfg);
        return source;
    }
}
