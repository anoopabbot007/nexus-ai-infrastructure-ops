package com.nexusai.client;

import com.fasterxml.jackson.databind.JsonNode;
import com.nexusai.api.IncidentRequest;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import java.util.Map;

@Component
public class HttpAgentClient implements AgentClient {
    private final RestClient restClient;
    public HttpAgentClient(RestClient.Builder builder, @Value("${agent-service.base-url}") String baseUrl) {
        this.restClient = builder.baseUrl(baseUrl).build();
    }
    @Override public JsonNode investigate(String incidentId, IncidentRequest request) {
        return restClient.post().uri("/investigate").contentType(MediaType.APPLICATION_JSON)
            .body(Map.of("incidentId", incidentId, "serviceName", request.serviceName(),
                "environment", request.environment(), "alertType", request.alertType(),
                "cpuUtilization", request.cpuUtilization() == null ? 0 : request.cpuUtilization(),
                "threshold", request.threshold() == null ? 80 : request.threshold(),
                "severity", request.severity(), "description", request.description()))
            .retrieve().body(JsonNode.class);
    }
}

