# InferCache: A Caching Gateway for ML Inference

A machine learning inference gateway built with **Java Spring Boot, Redis, and Python FastAPI**. The gateway caches sentiment analysis predictions to reduce repeated inference calls and improve response latency for repeated requests.

## Overview

Machine learning inference can be computationally expensive, particularly when requests repeatedly contain the same input. This project explores how a caching layer can improve the performance of an inference service.

The Java Spring Boot gateway receives prediction requests, checks Redis for a cached result, and forwards cache misses to a Python inference service running a pretrained DistilBERT model.

The project measures the latency difference between cache hits and cache misses and exposes basic cache statistics through a metrics endpoint.

## Architecture

```text
                  Client / Benchmark
                          |
                          v
                 Spring Boot Gateway
                     Port 8081
                          |
                    Normalize Input
                          |
                          v
                     Redis Cache
                     Port 6379
                          |
                 +--------+--------+
                 |                 |
              Cache HIT         Cache MISS
                 |                 |
                 v                 v
           Return Cached      Python FastAPI
             Prediction        Port 8000
                                   |
                                   v
                             DistilBERT Model
                                   |
                                   v
                            Return Prediction
                                   |
                                   v
                             Store in Redis
                                   |
                                   v
                           Return to Client
```

### Request flow

1. The client sends text to the Spring Boot prediction endpoint.
2. The gateway normalizes the input by trimming whitespace and converting it to lowercase for the cache key.
3. Redis is queried for a previously computed prediction.
4. On a **cache hit**, the cached prediction and confidence score are returned without invoking the model.
5. On a **cache miss**, the gateway calls the Python inference service, stores the result in Redis, and returns the prediction.
6. Cache entries expire after 60 seconds.

The original input text is sent to the inference service on a cache miss. Normalization is currently used to construct the cache key.

## Technology Stack

| Component        | Technology                                         |
| ---------------- | -------------------------------------------------- |
| Gateway          | Java 21, Spring Boot                               |
| Cache            | Redis 7                                            |
| Inference API    | Python, FastAPI                                    |
| ML framework     | PyTorch, Hugging Face Transformers                 |
| Model            | DistilBERT fine-tuned for SST-2 sentiment analysis |
| HTTP client      | Spring `RestClient`, Python `requests`             |
| Benchmarking     | Python, `time.perf_counter()`, `statistics`        |
| Containerization | Docker, for Redis                                  |

## Features

- **Inference gateway:** Routes prediction requests from the client to the ML service.
- **Cache-aside pattern:** Checks Redis before invoking the inference model.
- **Time-to-live:** Cached predictions expire after 60 seconds.
- **Sentiment analysis:** Uses a pretrained DistilBERT model to classify English text as positive or negative.
- **Latency benchmarking:** Compares response times for repeated inputs and unique inputs.
- **Cache metrics:** Exposes total requests, cache hits, cache misses, and cache-hit rate through an HTTP endpoint.

## Prerequisites

Install the following before running the project:

- Java 21 or a compatible configured Java runtime
- Python 3.11 or another version supported by the installed ML dependencies
- Docker Desktop
- Maven, or use the Maven Wrapper included with the Spring Boot project

The Python environment requires PyTorch, Transformers, FastAPI, Uvicorn, and Requests.

## Getting Started

### 1. Start Redis

Run Redis in Docker:

```powershell
docker run --name ml-proxy-redis -p 6379:6379 -d redis:7-alpine
```

If the container already exists, start it with:

```powershell
docker start ml-proxy-redis
```

Redis is configured in the Spring Boot application's `application.properties`:

```properties
spring.data.redis.host=localhost
spring.data.redis.port=6379
```

### 2. Start the Python inference service

Navigate to the Python service directory:

```powershell
cd "C:\Projects\Distributed Systems\ml-inference-proxy\python-service"
```

Install the required dependencies in your virtual environment if they are not already installed:

```powershell
.\.venv\Scripts\python.exe -m pip install fastapi uvicorn requests torch transformers
```

Start the inference service:

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000
```

The service loads the pretrained model during application startup and runs inference on the CPU.

You can inspect the interactive API documentation at:

`http://localhost:8000/docs`

### 3. Start the Spring Boot gateway

Open another terminal and navigate to the Spring Boot project directory:

```powershell
cd "C:\Projects\Distributed Systems\ml-inference-proxy\spring_boot\ml-inference-proxy"
```

Start the application:

```powershell
.\mvnw.cmd spring-boot:run
```

The gateway runs on port `8081`.

Ensure that the Python inference service and Redis are running before sending prediction requests.

## API Endpoints

### `POST /api/predict`

Accepts text and returns its sentiment prediction, confidence score, and cache status.

**Request**

```json
{
  "text": "The service is excellent and incredibly useful!"
}
```

**Example response: cache miss**

```json
{
  "input": "The service is excellent and incredibly useful!",
  "prediction": "positive",
  "confidence": 0.9999,
  "cache": "MISS"
}
```

**Example response: cache hit**

```json
{
  "input": "The service is excellent and incredibly useful!",
  "prediction": "positive",
  "confidence": 0.9999,
  "cache": "HIT"
}
```

The confidence values above are illustrative. Actual values depend on the input and model output.

You can test the endpoint using PowerShell:

```powershell
Invoke-RestMethod `
  -Uri "http://localhost:8081/api/predict" `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"text":"The service is excellent and incredibly useful!"}'
```

Send the same request again within the 60-second TTL to observe a cache hit.

### `GET /api/metrics`

Returns the gateway's in-memory cache statistics.

Open:

`http://localhost:8081/api/metrics`

Example response:

```json
{
  "totalRequests": 100,
  "cacheHits": 80,
  "cacheMisses": 20,
  "cacheHitRatePercent": 80.0
}
```

The values are illustrative. The metrics reset whenever the Spring Boot application restarts.

The cache-hit rate is calculated as:

[
\text{Hit Rate} =
\frac{\text{Cache Hits}}{\text{Total Requests}} \times 100
]

These counters currently track valid prediction requests and successful cache hits or misses. A failed inference request contributes to the total request count but is not counted as a completed cache miss.

## Benchmarking

The benchmark script, `benchmark.py`, compares two request patterns.

### Scenario 1: Cache hits

The same input is submitted repeatedly. After the initial cache entry is populated, subsequent requests should be served from Redis.

### Scenario 2: Cache misses

Each request uses a unique input. This prevents previous cache entries from being reused and forces the gateway to invoke the inference service.

The benchmark measures:

- Average latency
- Median latency
- 95th-percentile latency (P95)
- Minimum and maximum latency
- Average latency reduction
- Average speed ratio between cache misses and cache hits

The model is warmed up directly through the Python service before the measured gateway requests begin. The initial cache-population request is excluded from the cache-hit measurements.

### Run the benchmark

Ensure all three services are running, then execute:

```powershell
.\.venv\Scripts\python.exe benchmark.py
```

Run the script from the directory containing `benchmark.py`.

### Benchmark Results

The benchmark was run against the local inference gateway using 100 sequential requests per scenario.

| Metric          | Cache hit |  Cache miss |
| --------------- | --------: | ----------: |
| Requests        |       100 |         100 |
| Average latency |  39.46 ms |   531.93 ms |
| Median latency  |  25.62 ms |   484.84 ms |
| P95 latency     | 109.28 ms |   951.71 ms |
| Minimum latency |  11.88 ms |   212.56 ms |
| Maximum latency | 199.60 ms | 1,155.96 ms |

The cache-hit scenario achieved a **92.58% reduction in average end-to-end latency**, with cache hits approximately **13.48× faster on average** than cache misses in this experiment.

The measurements include HTTP and gateway overhead as well as inference latency for cache misses. Results reflect a local CPU-based environment and sequential requests; concurrent throughput and production-scale behavior have not yet been evaluated.

## Project Structure

```text
ml-inference-proxy/
├── python-service/
│   ├── main.py
│   └── benchmark.py
│
└── spring_boot/
    └── ml-inference-proxy/
        ├── pom.xml
        └── src/
            └── main/
                ├── java/
                │   └── com/caching/ml_inference_proxy/
                │       └── controller/
                │           └── PredictionController.java
                └── resources/
                    └── application.properties
```

- **`main.py`**: FastAPI service that runs DistilBERT sentiment analysis.
- **`benchmark.py`**: Measures cache-hit and cache-miss latency.
- **`pom.xml`**: Defines the Spring Boot project dependencies and build configuration.
- **`PredictionController.java`**: Handles prediction requests, Redis caching, and cache metrics.
- **`application.properties`**: Configures the Redis connection.

The Spring Boot directory name and exact internal package structure may differ depending on your local workspace.

## Current Limitations

- The inference service runs locally on the CPU; distributed or GPU inference is not currently implemented.
- The cache uses a 60-second TTL, which is configurable in the gateway code.
- Cache entries are keyed by normalized input text, without a model-version component.
- Cache metrics are stored in application memory and reset on restart.
- The current benchmark sends requests sequentially. Concurrent load and throughput testing have not yet been evaluated.
- The current implementation does not include authentication, production-grade observability, or multi-instance cache coordination.

## Potential Improvements

- Add concurrent-request and throughput benchmarking.
- Evaluate P95 and P99 latency under load.
- Measure cache-hit rate across different request distributions.
- Investigate concurrent requests for the same uncached input to reduce duplicate inference work.
- Add configurable TTLs and model-version-aware cache keys.
- Introduce structured monitoring and persistent metrics.
- Containerize the gateway and inference service for reproducible deployment.

## Learning Objectives

This project explores practical systems concepts through an ML inference workload:

- Request routing and service-to-service communication
- Cache-aside design and TTL-based expiration
- Latency measurement and performance comparison
- Tail-latency analysis
- Instrumentation and request metrics
- Trade-offs between computational cost, cache effectiveness, and response time

The goal is to evaluate these design choices through reproducible measurements rather than assume that caching or a particular architecture always improves performance.
