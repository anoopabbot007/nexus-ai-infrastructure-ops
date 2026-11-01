package com.nexusai.api;

import com.nexusai.service.AgentServiceException;
import com.nexusai.service.NotFoundException;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.*;
import java.time.Instant;
import java.util.Map;
import java.util.stream.Collectors;

@RestControllerAdvice
public class ApiExceptionHandler {
    @ExceptionHandler(NotFoundException.class) @ResponseStatus(HttpStatus.NOT_FOUND)
    ApiError notFound(NotFoundException ex) { return new ApiError(Instant.now(), 404, "Not Found", ex.getMessage(), Map.of()); }
    @ExceptionHandler(IllegalArgumentException.class) @ResponseStatus(HttpStatus.CONFLICT)
    ApiError conflict(IllegalArgumentException ex) { return new ApiError(Instant.now(), 409, "Conflict", ex.getMessage(), Map.of()); }
    @ExceptionHandler(AgentServiceException.class) @ResponseStatus(HttpStatus.BAD_GATEWAY)
    ApiError agentFailure(AgentServiceException ex) { return new ApiError(Instant.now(), 502, "Bad Gateway", ex.getMessage(), Map.of()); }
    @ExceptionHandler(MethodArgumentNotValidException.class) @ResponseStatus(HttpStatus.BAD_REQUEST)
    ApiError validation(MethodArgumentNotValidException ex) {
        Map<String, String> fields = ex.getBindingResult().getFieldErrors().stream().collect(Collectors.toMap(e -> e.getField(), e -> e.getDefaultMessage(), (a, b) -> a));
        return new ApiError(Instant.now(), 400, "Validation Failed", "Request validation failed", fields);
    }
}

