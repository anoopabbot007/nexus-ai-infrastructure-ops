package com.nexusai.domain;

import org.springframework.data.jpa.repository.JpaRepository;
import java.util.Optional;
import java.util.UUID;

public interface InvestigationRepository extends JpaRepository<InvestigationEntity, UUID> {
    Optional<InvestigationEntity> findByIncidentId(String incidentId);
}

