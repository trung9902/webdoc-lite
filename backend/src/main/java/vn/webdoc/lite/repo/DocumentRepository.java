package vn.webdoc.lite.repo;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;

import vn.webdoc.lite.domain.DocumentRecord;

public interface DocumentRepository extends JpaRepository<DocumentRecord, Long>, JpaSpecificationExecutor<DocumentRecord> {
}
