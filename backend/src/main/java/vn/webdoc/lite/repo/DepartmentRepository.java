package vn.webdoc.lite.repo;

import java.util.List;

import org.springframework.data.jpa.repository.JpaRepository;

import vn.webdoc.lite.domain.Department;

public interface DepartmentRepository extends JpaRepository<Department, Long> {
    List<Department> findByOrganizationIdAndStatusOrderByName(Long organizationId, int status);

    boolean existsByOrganizationIdAndNameIgnoreCaseAndStatus(Long organizationId, String name, int status);
}
