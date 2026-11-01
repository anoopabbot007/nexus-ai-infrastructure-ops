package com.nexusai.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.nexusai.api.IncidentRequest;
import com.nexusai.api.IncidentView;
import com.nexusai.client.AgentClient;
import com.nexusai.domain.IncidentEntity;
import com.nexusai.domain.IncidentRepository;
import com.nexusai.domain.InvestigationEntity;
import com.nexusai.domain.InvestigationRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.client.RestClientException;
import java.util.List;
import java.util.UUID;

@Service
public class IncidentService {
    private final IncidentRepository incidents;
    private final InvestigationRepository investigations;
    private final AgentClient agentClient;

    public IncidentService(IncidentRepository incidents, InvestigationRepository investigations, AgentClient agentClient) {
        this.incidents = incidents; this.investigations = investigations; this.agentClient = agentClient;
    }

    @Transactional(noRollbackFor = AgentServiceException.class)
    public IncidentView create(IncidentRequest request) {
        String id = request.incidentId() == null || request.incidentId().isBlank() ? "INC-" + UUID.randomUUID().toString().substring(0, 8).toUpperCase() : request.incidentId();
        if (incidents.findByIncidentId(id).isPresent()) throw new IllegalArgumentException("Incident ID already exists: " + id);
        IncidentEntity incident = new IncidentEntity();
        incident.setIncidentId(id); incident.setServiceName(request.serviceName()); incident.setEnvironment(request.environment());
        incident.setAlertType(request.alertType()); incident.setSeverity(request.severity()); incident.setDescription(request.description()); incident.setStatus("INVESTIGATING");
        incidents.saveAndFlush(incident);
        try {
            JsonNode report = agentClient.investigate(id, request);
            IncidentEntity saved = incidents.findByIncidentId(id).orElseThrow();
            String workflowStatus = report.path("executionStatus").asText("FAILED");
            saved.setStatus(workflowStatus.equals("COMPLETED") ? "COMPLETED" : "FAILED");
            InvestigationEntity investigation = toInvestigation(id, report);
            investigations.save(investigation);
            return view(saved, investigation);
        } catch (RestClientException ex) {
            incidents.findByIncidentId(id).ifPresent(saved -> saved.setStatus("FAILED"));
            throw new AgentServiceException("Agent service could not complete the investigation", ex);
        }
    }

    @Transactional(readOnly = true)
    public List<IncidentView> list() { return incidents.findAll().stream().map(i -> view(i, investigations.findByIncidentId(i.getIncidentId()).orElse(null))).toList(); }

    @Transactional(readOnly = true)
    public IncidentView get(String id) { return view(requireIncident(id), investigations.findByIncidentId(id).orElse(null)); }

    @Transactional(readOnly = true)
    public Object report(String id) {
        requireIncident(id);
        return investigations.findByIncidentId(id).map(InvestigationEntity::getReport).orElseThrow(() -> new NotFoundException("Report not found for incident " + id));
    }

    private IncidentEntity requireIncident(String id) { return incidents.findByIncidentId(id).orElseThrow(() -> new NotFoundException("Incident not found: " + id)); }
    private IncidentView view(IncidentEntity i, InvestigationEntity result) { return new IncidentView(i.getIncidentId(), i.getServiceName(), i.getEnvironment(), i.getAlertType(), i.getSeverity(), i.getDescription(), i.getStatus(), i.getCreatedAt(), i.getUpdatedAt(), result == null ? null : result.getReport()); }
    private InvestigationEntity toInvestigation(String id, JsonNode report) {
        InvestigationEntity entity = new InvestigationEntity(); entity.setIncidentId(id);
        entity.setRootCause(report.path("probableRootCause").asText("No root cause returned"));
        entity.setConfidenceScore(report.path("confidenceScore").asDouble(0));
        entity.setInvestigationFindings(report.path("investigationFindings")); entity.setRecommendedActions(report.path("recommendedActions"));
        entity.setExecutionTrace(report.path("executionTrace")); entity.setInfrastructureMetrics(report.path("infrastructureMetrics"));
        entity.setApplicationLogs(report.path("applicationLogs")); entity.setReport(report); entity.setLlmProvider(report.path("llmProvider").asText("unknown"));
        return entity;
    }
}

