package vn.webdoc.lite.repo;

import java.util.Optional;

import org.springframework.data.jpa.repository.JpaRepository;

import vn.webdoc.lite.domain.Organization;

public interface OrganizationRepository extends JpaRepository<Organization, Long> {
    Optional<Organization> findByCode(String code);
}
