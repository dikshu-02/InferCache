
import statistics
import time
import uuid

import requests


JAVA_URL = "http://localhost:8081/api/predict"
PYTHON_URL = "http://localhost:8000/predict"

REQUEST_COUNT = 100
TIMEOUT_SECONDS = 60


def send_request(url, text):
    start = time.perf_counter()

    response = requests.post(
        url,
        json={"text": text},
        timeout=TIMEOUT_SECONDS,
    )

    response.raise_for_status()
    elapsed_ms = (time.perf_counter() - start) * 1000

    return elapsed_ms, response.json()


def percentile(latencies, percent):
    ordered = sorted(latencies)
    index = int((percent / 100) * (len(ordered) - 1))
    return ordered[index]


def report_results(label, latencies):
    print(f"\n{label}")
    print("-" * 40)
    print(f"Requests:        {len(latencies)}")
    print(f"Average latency: {statistics.mean(latencies):.2f} ms")
    print(f"Median latency:  {statistics.median(latencies):.2f} ms")
    print(f"P95 latency:     {percentile(latencies, 95):.2f} ms")
    print(f"Min latency:     {min(latencies):.2f} ms")
    print(f"Max latency:     {max(latencies):.2f} ms")


def main():
    # Step 1: Warm up the actual model directly, bypassing Redis.
    print("Warming up the Python inference model...")

    for i in range(3):
        _, result = send_request(
            PYTHON_URL,
            f"Model warm-up request number {i}.",
        )

    print(f"Direct inference response: {result}")
    print("Model warm-up complete.")

    # Step 2: Warm up the Java-to-Python request path.
    warmup_text = f"Gateway warm-up {uuid.uuid4()}"

    _, warmup_result = send_request(JAVA_URL, warmup_text)
    print(f"\nGateway warm-up response: {warmup_result}")

    # Step 3: Create a fresh cache entry for the HIT test.
    # A unique suffix avoids an entry left over from an earlier run.
    repeated_text = (
        "The service is excellent and incredibly useful! "
        f"{uuid.uuid4()}"
    )

    _, initial_result = send_request(JAVA_URL, repeated_text)
    print(f"\nInitial cache-population response: {initial_result}")

    if initial_result.get("cache") != "MISS":
        raise RuntimeError(
            f"Expected initial cache MISS, got: {initial_result}"
        )

    # Step 4: Measure requests served from Redis.
    hit_latencies = []

    for _ in range(REQUEST_COUNT):
        elapsed_ms, result = send_request(JAVA_URL, repeated_text)

        if result.get("cache") != "HIT":
            raise RuntimeError(
                f"Expected cache HIT, got: {result}"
            )

        hit_latencies.append(elapsed_ms)

    report_results("CACHE HIT: repeated input", hit_latencies)

    # Step 5: Measure requests that require actual model inference.
    miss_latencies = []

    for i in range(REQUEST_COUNT):
        unique_text = (
            f"Unique benchmark review {i} {uuid.uuid4()}. "
            "The service is excellent and useful."
        )

        elapsed_ms, result = send_request(JAVA_URL, unique_text)

        if result.get("cache") != "MISS":
            raise RuntimeError(
                f"Expected cache MISS, got: {result}"
            )

        miss_latencies.append(elapsed_ms)

    report_results("CACHE MISS: unique inputs", miss_latencies)

    # Step 6: Compare the two scenarios.
    hit_average = statistics.mean(hit_latencies)
    miss_average = statistics.mean(miss_latencies)

    hit_median = statistics.median(hit_latencies)
    miss_median = statistics.median(miss_latencies)

    print("\nCOMPARISON")
    print("-" * 40)
    print(f"Average HIT latency:  {hit_average:.2f} ms")
    print(f"Average MISS latency: {miss_average:.2f} ms")
    print(f"Median HIT latency:   {hit_median:.2f} ms")
    print(f"Median MISS latency:  {miss_median:.2f} ms")

    if miss_average > 0:
        reduction = (
            (miss_average - hit_average) / miss_average
        ) * 100

        print(f"Average latency reduction: {reduction:.2f}%")

        if hit_average > 0:
            print(
                f"Average speed ratio: "
                f"{miss_average / hit_average:.2f}x"
            )


if __name__ == "__main__":
    main()
