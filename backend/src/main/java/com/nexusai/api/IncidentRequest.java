package com.nexusai.api;

import jakarta.validation.constraints.*;

public record IncidentRequest(
    @Size(min = 3, max = 80) String incidentId,
    @NotBlank @Size(max = 120) String serviceName,
    @NotBlank @Size(max = 40) String environment,
    @NotBlank @Size(max = 80) String alertType,
    @DecimalMin("0.0") @DecimalMax("100.0") Double cpuUtilization,
    @DecimalMin("0.0") @DecimalMax("100.0") Double threshold,
    @NotBlank @Pattern(regexp = "LOW|MEDIUM|HIGH|CRITICAL") String severity,
    @NotBlank @Size(min = 5, max = 2000) String description
) {}

