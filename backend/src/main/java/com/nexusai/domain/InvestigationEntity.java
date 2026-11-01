package com.nexusai.domain;

import com.fasterxml.jackson.databind.JsonNode;
import jakarta.persistence.*;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "investigations")
public class InvestigationEntity {
    @Id @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;
    @Column(name = "incident_id", nullable = false, unique = true, length = 80)
    private String incidentId;
    @Column(name = "root_cause", nullable = false, columnDefinition = "text")
    private String rootCause;
    @Column(name = "confidence_score", nullable = false)
    private double confidenceScore;
    @JdbcTypeCode(SqlTypes.JSON) @Column(name = "investigation_findings", nullable = false, columnDefinition = "jsonb")
    private JsonNode investigationFindings;
    @JdbcTypeCode(SqlTypes.JSON) @Column(name = "recommended_actions", nullable = false, columnDefinition = "jsonb")
    private JsonNode recommendedActions;
    @JdbcTypeCode(SqlTypes.JSON) @Column(name = "execution_trace", nullable = false, columnDefinition = "jsonb")
    private JsonNode executionTrace;
    @JdbcTypeCode(SqlTypes.JSON) @Column(name = "infrastructure_metrics", nullable = false, columnDefinition = "jsonb")
    private JsonNode infrastructureMetrics;
    @JdbcTypeCode(SqlTypes.JSON) @Column(name = "application_logs", nullable = false, columnDefinition = "jsonb")
    private JsonNode applicationLogs;
    @JdbcTypeCode(SqlTypes.JSON) @Column(name = "report", nullable = false, columnDefinition = "jsonb")
    private JsonNode report;
    @Column(name = "llm_provider", nullable = false, length = 40)
    private String llmProvider;
    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    @PrePersist void onCreate() { createdAt = Instant.now(); }
    public UUID getId() { return id; }
    public String getIncidentId() { return incidentId; }
    public void setIncidentId(String v) { incidentId = v; }
    public String getRootCause() { return rootCause; }
    public void setRootCause(String v) { rootCause = v; }
    public double getConfidenceScore() { return confidenceScore; }
    public void setConfidenceScore(double v) { confidenceScore = v; }
    public JsonNode getInvestigationFindings() { return investigationFindings; }
    public void setInvestigationFindings(JsonNode v) { investigationFindings = v; }
    public JsonNode getRecommendedActions() { return recommendedActions; }
    public void setRecommendedActions(JsonNode v) { recommendedActions = v; }
    public JsonNode getExecutionTrace() { return executionTrace; }
    public void setExecutionTrace(JsonNode v) { executionTrace = v; }
    public JsonNode getInfrastructureMetrics() { return infrastructureMetrics; }
    public void setInfrastructureMetrics(JsonNode v) { infrastructureMetrics = v; }
    public JsonNode getApplicationLogs() { return applicationLogs; }
    public void setApplicationLogs(JsonNode v) { applicationLogs = v; }
    public JsonNode getReport() { return report; }
    public void setReport(JsonNode v) { report = v; }
    public String getLlmProvider() { return llmProvider; }
    public void setLlmProvider(String v) { llmProvider = v; }
    public Instant getCreatedAt() { return createdAt; }
}

