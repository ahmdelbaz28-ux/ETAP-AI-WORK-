# ETAP-AI Engineering Service Helm Chart

This Helm chart deploys the ETAP-AI Engineering Service with production-ready scalability features including async task queues and real-time WebSocket communication.

## Architecture Overview

The deployment consists of:

- **API Service**: Handles HTTP requests and WebSocket connections
- **Celery Workers**: Process heavy engineering tasks asynchronously
- **Redis**: Acts as message broker for task queue and caching backend
- **WebSocket**: Provides real-time SCADA data streaming

## Request Flow for "Run Study" Operation

When a user clicks "Run Study", the following happens:

1. **Client Request**: User submits study request to `/api/v1/studies/run_async`
2. **API Receives**: Engineering service validates request and parameters
3. **Task Queuing**: Instead of blocking, API pushes study job to Redis queue via Celery
4. **Immediate Response**: API returns `task_id` to client immediately
5. **Worker Processing**: Celery worker picks up task from queue and executes study
6. **Progress Tracking**: Client can poll `/api/v1/studies/task_status/{task_id}` for progress
7. **Completion**: When complete, results available via task status endpoint

## Request Flow for Real-time SCADA Data

For real-time SCADA data:

1. **WebSocket Connection**: Client connects to `/ws/scada/live`
2. **Continuous Feed**: Server broadcasts SCADA measurements every 1 second
3. **Multiple Clients**: All connected clients receive same real-time data
4. **Automatic Reconnect**: Built-in reconnection logic on connection loss

## Installation

```bash
# Add the dependency chart repo
helm repo add bitnami https://charts.bitnami.com/bitnami

# Install the chart
helm install etap-ai ./helm/etap-ai \
  --set api.replicaCount=2 \
  --set worker.replicaCount=2 \
  --set env.ENGINEERING_SERVICE_API_KEY="your-api-key"
```

## Values

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `api.replicaCount` | int | `2` | Number of API server replicas |
| `worker.replicaCount` | int | `2` | Number of Celery worker replicas |
| `env.USE_ETAP` | string | `"false"` | Enable/disable ETAP integration |
| `env.PRIVACY_MODE` | string | `"true"` | Enable/disable external telemetry |
| `env.ENGINEERING_SERVICE_API_KEY` | string | `""` | API authentication key |

## Production Considerations

- Use a proper ingress controller (nginx, traefik) for external access
- Configure SSL certificates for secure connections
- Set up proper monitoring and alerting
- Use Kubernetes secrets for sensitive configuration
- Implement resource quotas and limits
- Configure backup strategies for persistent volumes