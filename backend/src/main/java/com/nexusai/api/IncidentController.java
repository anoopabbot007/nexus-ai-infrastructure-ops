package com.nexusai.api;

import com.nexusai.service.IncidentService;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;
import java.util.List;

@RestController
@RequestMapping("/api/v1/incidents")
public class IncidentController {
    private final IncidentService service;
    public IncidentController(IncidentService service) { this.service = service; }
    @PostMapping @ResponseStatus(HttpStatus.CREATED) public IncidentView create(@Valid @RequestBody IncidentRequest request) { return service.create(request); }
    @GetMapping public List<IncidentView> list() { return service.list(); }
    @GetMapping("/{incidentId}") public IncidentView get(@PathVariable String incidentId) { return service.get(incidentId); }
    @GetMapping("/{incidentId}/report") public Object report(@PathVariable String incidentId) { return service.report(incidentId); }
}

