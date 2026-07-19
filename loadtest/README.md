# ArenaMind-AI Load Testing

This directory contains a Locust load test suite designed to evaluate the real-world performance, rate-limiting, and error-handling capabilities of the ArenaMind-AI backend under simulated fan traffic.

## Requirements

The load tests use [Locust](https://locust.io/), an open-source load testing tool. It is kept separate from the main application dependencies to keep the production container lean.

```bash
pip install -r loadtest/requirements.txt
```

## Running the Load Test

### Against the Live Render Deployment

To run the load test against the public Render URL in headless mode (no web UI), export a valid fan token and point Locust to the host:

```bash
# macOS/Linux
export FAN_AUTH_TOKEN="your_real_fan_token"

# Windows (PowerShell)
$env:FAN_AUTH_TOKEN="your_real_fan_token"

locust -f loadtest/locustfile.py --headless -u 10 -r 2 --run-time 2m --host=https://arenamind-ai.onrender.com
```

### Against a Local Dev Server

For safer iteration without incurring cloud costs or triggering Render's abuse filters, test against your local `uvicorn` instance:

```bash
locust -f loadtest/locustfile.py --headless -u 10 -r 2 --run-time 2m --host=http://localhost:8080
```

---

## Load Test Baseline Observations

When running this test against the live URL with a modest configuration (10 concurrent users, spawning at 2 users/sec, 1-5 seconds of think-time), we observed the following behaviors:

### 1. Rate Limiting (429 Too Many Requests)
The `slowapi` rate limiter is configured for `15/minute` per IP address on the `/api/v1/operations/query` and `/stream` endpoints.
- **Observed:** Because Locust routes all simulated users from your single local IP address, the 15-request threshold is hit almost immediately (within the first ~10 seconds). After 15 requests, the server correctly and consistently returns HTTP 429 until the minute rolls over.
- **Result:** The rate limiter works perfectly to protect the LLM backend from sudden spikes from a single source.

### 2. Authorization (401 Unauthorized)
- **Observed:** If the `FAN_AUTH_TOKEN` environment variable is missing, incorrect, or mismatched with the live server's `.env` file, the `dependencies.py` RBAC check immediately intercepts the request.
- **Result:** Locust accurately records 100% `401 Unauthorized` failures with the message *"Unauthorized - check FAN_AUTH_TOKEN environment variable"*. This proves the security guardrail executes *before* the rate limiter or the LLM logic.

### 3. Latency & External Failures (500 Internal Server Error)
- **Observed:** When testing locally with a mock `GEMINI_API_KEY`, requests pass authentication but fail during the `OperationalBrain.generate_response()` phase. The Google API SDK waits for a response and ultimately throws a `google.api_core.exceptions.InvalidArgument: 400 API key not valid`.
- **Result:** The server returns a `500 Internal Server Error`. Because the Google API call blocks for ~1.5 to 2.5 seconds before failing, the p50 latency is artificially inflated. This confirms that upstream Gemini API latency directly dictates our endpoint latency, emphasizing the need for the asynchronous streaming endpoint.

### 4. Streaming Endpoint
- **Observed:** The `/stream` endpoint successfully handles Server-Sent Events when authenticated. However, under high load, if the Gemini API throttles the connection, the streaming timeout circuit-breaker (the 15-second `time.monotonic()` loop) successfully aborts hung streams and yields an error chunk rather than leaving dangling connections.

> ⚠️ **Warning:** Do not run large-scale load tests against the live `arenamind-ai.onrender.com` URL. The Render Free/Hobby tier has strict resource constraints, and the Google Gemini API has hard quotas. Large tests will incur API costs or result in service suspension.
