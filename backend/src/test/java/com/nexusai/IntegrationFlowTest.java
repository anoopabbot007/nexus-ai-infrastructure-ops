package com.nexusai;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.nexusai.client.AgentClient;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@Testcontainers(disabledWithoutDocker = true)
class IntegrationFlowTest {
    @Container static final PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:16-alpine");
    @Autowired MockMvc mvc;
    @Autowired ObjectMapper objectMapper;
    @MockitoBean AgentClient agentClient;

    @DynamicPropertySource
    static void databaseProperties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", postgres::getJdbcUrl);
        registry.add("spring.datasource.username", postgres::getUsername);
        registry.add("spring.datasource.password", postgres::getPassword);
    }

    @Test void persistsIncidentAndInvestigationReportAcrossApiRequests() throws Exception {
        when(agentClient.investigate(anyString(), any())).thenReturn(objectMapper.readTree("""
            {"incidentId":"INC-IT-100","severity":"CRITICAL","affectedService":"payment-service","investigationParameters":["cpu"],
             "infrastructureMetrics":[{"id":"cpu-1","name":"cpu_utilization","value":94}],"applicationLogs":[],
             "investigationFindings":[{"title":"signals","summary":"cpu elevated","evidenceIds":["cpu-1"]}],
             "probableRootCause":"Excessive application thread creation","confidenceScore":0.92,"reasoning":"thread count high",
             "recommendedActions":[{"title":"Review thread pool","description":"inspect","expectedImpact":"reduce CPU","risk":"MEDIUM","verificationSteps":["check p95"]}],
             "executionStatus":"COMPLETED","errors":[],"executionTrace":[],"llmProvider":"mock"}
            """));

        mvc.perform(post("/api/v1/incidents").contentType(MediaType.APPLICATION_JSON).content("""
                {"incidentId":"INC-IT-100","serviceName":"payment-service","environment":"production","alertType":"HIGH_CPU","cpuUtilization":94,"threshold":80,"severity":"CRITICAL","description":"CPU utilization exceeded threshold"}
                """))
            .andExpect(status().isCreated())
            .andExpect(jsonPath("$.status").value("COMPLETED"))
            .andExpect(jsonPath("$.investigation.probableRootCause").value("Excessive application thread creation"));

        mvc.perform(get("/api/v1/incidents/INC-IT-100/report"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.infrastructureMetrics[0].id").value("cpu-1"))
            .andExpect(jsonPath("$.recommendedActions[0].risk").value("MEDIUM"));
    }
}
