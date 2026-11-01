package com.nexusai.domain;

import org.springframework.data.jpa.repository.JpaRepository;
import java.util.Optional;
import java.util.UUID;

public interface IncidentRepository extends JpaRepository<IncidentEntity, UUID> {
    Optional<IncidentEntity> findByIncidentId(String incidentId);
}

