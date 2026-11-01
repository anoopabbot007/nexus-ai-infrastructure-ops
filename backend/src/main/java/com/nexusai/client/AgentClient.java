package com.nexusai.client;

import com.fasterxml.jackson.databind.JsonNode;
import com.nexusai.api.IncidentRequest;

public interface AgentClient {
    JsonNode investigate(String incidentId, IncidentRequest request);
}

