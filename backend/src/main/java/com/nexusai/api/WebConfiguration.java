package com.nexusai.api;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

@Configuration
public class WebConfiguration implements WebMvcConfigurer {
    private final String[] origins;
    public WebConfiguration(@Value("${app.cors.allowed-origins}") String allowedOrigins) {
        this.origins = allowedOrigins.split(",");
    }
    @Override public void addCorsMappings(CorsRegistry registry) {
        registry.addMapping("/api/**").allowedOrigins(origins).allowedMethods("GET", "POST", "OPTIONS").allowedHeaders("Content-Type", "Authorization");
    }
}
