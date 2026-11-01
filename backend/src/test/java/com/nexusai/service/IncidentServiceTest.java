package com.nexusai.service;

import com.nexusai.api.IncidentRequest;
import com.nexusai.client.AgentClient;
import com.nexusai.domain.IncidentEntity;
import com.nexusai.domain.IncidentRepository;
import com.nexusai.domain.InvestigationRepository;
import org.junit.jupiter.api.Test;
import java.util.Optional;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

class IncidentServiceTest {
    @Test void duplicateIncidentIdIsRejected() {
        IncidentRepository incidentRepository = mock(IncidentRepository.class);
        InvestigationRepository investigationRepository = mock(InvestigationRepository.class);
        AgentClient client = mock(AgentClient.class);
        when(incidentRepository.findByIncidentId("INC-DUP")).thenReturn(Optional.of(new IncidentEntity()));
        IncidentService service = new IncidentService(incidentRepository, investigationRepository, client);
        IncidentRequest request = new IncidentRequest("INC-DUP", "orders", "staging", "HIGH_CPU", 90.0, 80.0, "HIGH", "CPU utilization above threshold");
        assertThrows(IllegalArgumentException.class, () -> service.create(request));
        verifyNoInteractions(client);
    }
    @Test void downstreamFailureMarksSavedIncidentFailed() {
        IncidentRepository incidentRepository = mock(IncidentRepository.class);
        InvestigationRepository investigationRepository = mock(InvestigationRepository.class);
        AgentClient client = mock(AgentClient.class);
        IncidentEntity entity = new IncidentEntity();
        when(incidentRepository.findByIncidentId("INC-FAIL")).thenReturn(Optional.empty(), Optional.of(entity));
        when(incidentRepository.saveAndFlush(any(IncidentEntity.class))).thenAnswer(invocation -> (IncidentEntity) invocation.getArgument(0));
        when(client.investigate(any(), any())).thenThrow(new org.springframework.web.client.ResourceAccessException("down"));
        IncidentService service = new IncidentService(incidentRepository, investigationRepository, client);
        IncidentRequest request = new IncidentRequest("INC-FAIL", "orders", "staging", "HIGH_CPU", 90.0, 80.0, "HIGH", "CPU utilization above threshold");
        assertThrows(AgentServiceException.class, () -> service.create(request));
        assertEquals("FAILED", entity.getStatus());
    }
}
