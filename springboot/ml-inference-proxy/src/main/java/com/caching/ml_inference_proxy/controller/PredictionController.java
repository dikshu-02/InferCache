
package com.caching.ml_inference_proxy.controller;

import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestClient;

import java.util.Map;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;

@RestController
@RequestMapping("/api")
public class PredictionController {

    private final RestClient restClient;
    private final StringRedisTemplate redisTemplate;

    // Track request and cache statistics.
    private final AtomicLong totalRequests = new AtomicLong();
    private final AtomicLong cacheHits = new AtomicLong();
    private final AtomicLong cacheMisses = new AtomicLong();

    public PredictionController(StringRedisTemplate redisTemplate) {
        this.restClient = RestClient.builder()
                .baseUrl("http://localhost:8000")
                .build();

        this.redisTemplate = redisTemplate;
    }

    @PostMapping("/predict")
    public Map<String, Object> predict(
            @RequestBody Map<String, String> request) {

        String text = request.get("text");

        if (text == null || text.isBlank()) {
            throw new IllegalArgumentException(
                    "The text field must not be empty");
        }

        totalRequests.incrementAndGet();

        String normalizedText = text.trim().toLowerCase();
        String cacheKey = "prediction:" + normalizedText;

        String cachedPrediction = redisTemplate.opsForValue()
                .get(cacheKey);

        if (cachedPrediction != null) {
            cacheHits.incrementAndGet();

            String[] parts = cachedPrediction.split("\\|", 2);

            return Map.of(
                    "input", text,
                    "prediction", parts[0],
                    "confidence", Double.parseDouble(parts[1]),
                    "cache", "HIT"
            );
        }

        Map<String, Object> response = restClient.post()
                .uri("/predict")
                .body(Map.of("text", text))
                .retrieve()
                .body(Map.class);

        if (response == null
                || response.get("prediction") == null
                || response.get("confidence") == null) {
            throw new IllegalStateException(
                    "Python inference service returned an invalid response");
        }

        String prediction = response.get("prediction").toString();
        double confidence = Double.parseDouble(
                response.get("confidence").toString());

        redisTemplate.opsForValue().set(
                cacheKey,
                prediction + "|" + confidence,
                60,
                TimeUnit.SECONDS
        );

        cacheMisses.incrementAndGet();

        return Map.of(
                "input", text,
                "prediction", prediction,
                "confidence", confidence,
                "cache", "MISS"
        );
    }

    @GetMapping("/metrics")
    public Map<String, Object> metrics() {
        long total = totalRequests.get();
        long hits = cacheHits.get();
        long misses = cacheMisses.get();

        double hitRate = total == 0
                ? 0.0
                : (hits * 100.0) / total;

        return Map.of(
                "totalRequests", total,
                "cacheHits", hits,
                "cacheMisses", misses,
                "cacheHitRatePercent",
                Math.round(hitRate * 100.0) / 100.0
        );
    }
}
