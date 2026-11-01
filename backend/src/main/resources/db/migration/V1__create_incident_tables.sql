CREATE TABLE incidents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id VARCHAR(80) NOT NULL UNIQUE,
    service_name VARCHAR(120) NOT NULL,
    environment VARCHAR(40) NOT NULL,
    alert_type VARCHAR(80) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    description VARCHAR(2000) NOT NULL,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE investigations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id VARCHAR(80) NOT NULL UNIQUE REFERENCES incidents(incident_id) ON DELETE CASCADE,
    root_cause TEXT NOT NULL,
    confidence_score DOUBLE PRECISION NOT NULL CHECK (confidence_score >= 0 AND confidence_score <= 1),
    investigation_findings JSONB NOT NULL,
    recommended_actions JSONB NOT NULL,
    execution_trace JSONB NOT NULL,
    infrastructure_metrics JSONB NOT NULL,
    application_logs JSONB NOT NULL,
    report JSONB NOT NULL,
    llm_provider VARCHAR(40) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_incidents_created_at ON incidents(created_at DESC);
