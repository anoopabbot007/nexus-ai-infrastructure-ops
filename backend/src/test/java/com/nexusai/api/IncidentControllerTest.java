package com.nexusai.api;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.nexusai.service.IncidentService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import java.time.Instant;
import java.util.List;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@WebMvcTest(IncidentController.class)
class IncidentControllerTest {
    @Autowired MockMvc mvc;
    @Autowired ObjectMapper mapper;
    @MockitoBean IncidentService service;
    @Test void createsAnIncidentThroughTheService() throws Exception {
        IncidentRequest request = new IncidentRequest("INC-1001", "payment-service", "production", "HIGH_CPU", 94.0, 80.0, "CRITICAL", "CPU utilization exceeded 80% for 10 minutes");
        when(service.create(any())).thenReturn(new IncidentView("INC-1001", "payment-service", "production", "HIGH_CPU", "CRITICAL", request.description(), "COMPLETED", Instant.parse("2026-11-01T10:00:00Z"), Instant.parse("2026-11-01T10:00:00Z"), null));
        mvc.perform(post("/api/v1/incidents").contentType(MediaType.APPLICATION_JSON).content(mapper.writeValueAsString(request))).andExpect(status().isCreated()).andExpect(jsonPath("$.incidentId").value("INC-1001")).andExpect(jsonPath("$.status").value("COMPLETED"));
        verify(service).create(any());
    }
    @Test void listsIncidents() throws Exception {
        when(service.list()).thenReturn(List.of());
        mvc.perform(get("/api/v1/incidents")).andExpect(status().isOk()).andExpect(content().json("[]"));
    }
    @Test void validatesRequiredIncidentFields() throws Exception {
        mvc.perform(post("/api/v1/incidents").contentType(MediaType.APPLICATION_JSON).content("{\"serviceName\":\"\"}")).andExpect(status().isBadRequest()).andExpect(jsonPath("$.fields.serviceName").exists());
        verifyNoInteractions(service);
    }
}
