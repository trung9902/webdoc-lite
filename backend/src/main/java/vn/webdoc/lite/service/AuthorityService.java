package vn.webdoc.lite.service;

import java.util.Collection;
import java.util.LinkedHashSet;
import java.util.Set;

import org.springframework.security.authentication.BadCredentialsException;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import lombok.RequiredArgsConstructor;
import vn.webdoc.lite.domain.UserAccount;
import vn.webdoc.lite.repo.UserRepository;

/** Dựng danh sách quyền của Spring Security từ CSDL ở mỗi yêu cầu. */
@Service
@RequiredArgsConstructor
public class AuthorityService {
    private final UserRepository users;
    private final PermissionService permissions;

    @Transactional(readOnly = true)
    public Collection<GrantedAuthority> authoritiesOf(String username) {
        UserAccount user = users.findByUsernameIgnoreCase(username)
                .filter(u -> u.getStatus() == 1)
                .orElseThrow(() -> new BadCredentialsException("Tài khoản không hợp lệ hoặc đã bị khoá"));
        Set<GrantedAuthority> set = new LinkedHashSet<>();
        user.getRoles().forEach(r -> set.add(new SimpleGrantedAuthority("ROLE_" + r.getCode())));
        permissions.effective(user).forEach(p -> set.add(new SimpleGrantedAuthority(p)));
        if (user.isAdmin()) {
            set.add(new SimpleGrantedAuthority("ROLE_SYSTEM_ADMIN"));
        }
        if (user.isOrganizationManager()) {
            set.add(new SimpleGrantedAuthority("ROLE_ORG_MANAGER"));
        }
        return set;
    }
}
