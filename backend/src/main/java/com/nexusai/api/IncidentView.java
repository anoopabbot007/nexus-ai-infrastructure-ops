package com.nexusai.api;

import java.time.Instant;

public record IncidentView(String incidentId, String serviceName, String environment, String alertType,
                           String severity, String description, String status, Instant createdAt,
                           Instant updatedAt, Object investigation) {}

