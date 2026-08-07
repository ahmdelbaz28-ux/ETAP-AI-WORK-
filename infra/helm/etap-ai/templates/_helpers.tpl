{{/*
Expand the name of the chart.
*/}}
{{- define "etap-ai.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this
(by the DNS naming spec).
*/}}
{{- define "etap-ai.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "etap-ai.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Common labels
*/}}
{{- define "etap-ai.labels" -}}
helm.sh/chart: {{ include "etap-ai.chart" . }}
{{ include "etap-ai.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: etap-ai-platform
{{- end -}}

{{/*
Selector labels
*/}}
{{- define "etap-ai.selectorLabels" -}}
app.kubernetes.io/name: {{ include "etap-ai.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{/*
Service account name
*/}}
{{- define "etap-ai.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{- default (include "etap-ai.fullname" .) .Values.serviceAccount.name -}}
{{- else -}}
{{- default "default" .Values.serviceAccount.name -}}
{{- end -}}
{{- end -}}

{{/*
Resolve image reference for a given component.
Usage: {{ include "etap-ai.image" (list . .Values.api.image) }}
*/}}
{{- define "etap-ai.image" -}}
{{- $root := index . 0 -}}
{{- $img  := index . 1 -}}
{{- $repo := $img.repository -}}
{{- if not $repo -}}{{- $repo = $root.Values.image.repository -}}{{- end -}}
{{- $tag  := $img.tag -}}
{{- if not $tag -}}{{- $tag = $root.Values.image.tag | default $root.Chart.AppVersion -}}{{- end -}}
{{- $pull := $img.pullPolicy -}}
{{- if not $pull -}}{{- $pull = $root.Values.image.pullPolicy -}}{{- end -}}
{{- printf "%s%s:%s" $root.Values.global.imageRegistry $repo $tag -}}
{{- end -}}

{{/* =========================================================================
   Redis URL parsing helpers.
   Input .Values.redis.url is expected to be one of:
     - redis://host:port/db        (no auth)
     - redis://host:port           (no auth, default db 0)
     - rediss://host:port/db       (TLS, no auth)
   The password (if any) is NEVER embedded in the URL here. It is injected
   as a separate REDIS_PASSWORD env var and expanded via $(REDIS_PASSWORD).
   ========================================================================= */}}

{{- define "etap-ai.redisScheme" -}}
{{- $url := .Values.redis.url -}}
{{- if hasPrefix "rediss://" $url -}}rediss{{- else -}}redis{{- end -}}
{{- end -}}

{{- define "etap-ai.redisHostPort" -}}
{{- $url := .Values.redis.url -}}
{{- $stripped := trimPrefix "rediss://" $url | trimPrefix "redis://" -}}
{{- $hostPort := splitList "/" $stripped | first -}}
{{- $hostPort -}}
{{- end -}}

{{- define "etap-ai.redisHost" -}}
{{- $hp := include "etap-ai.redisHostPort" . -}}
{{- $host := splitList ":" $hp | first -}}
{{- $host -}}
{{- end -}}

{{- define "etap-ai.redisPort" -}}
{{- $hp := include "etap-ai.redisHostPort" . -}}
{{- $parts := splitList ":" $hp -}}
{{- if eq (len $parts) 2 -}}{{- index $parts 1 -}}{{- else -}}6379{{- end -}}
{{- end -}}

{{- define "etap-ai.redisDb" -}}
{{- $url := .Values.redis.url -}}
{{- $stripped := trimPrefix "rediss://" $url | trimPrefix "redis://" -}}
{{- $parts := splitList "/" $stripped -}}
{{- if gt (len $parts) 1 -}}{{- index $parts 1 -}}{{- else -}}0{{- end -}}
{{- end -}}

{{/*
Build the REDIS_URL with $(REDIS_PASSWORD) placeholder.
The placeholder is expanded at pod-startup time using the REDIS_PASSWORD
env var, which MUST be defined earlier in the same container's env list.
*/}}
{{- define "etap-ai.redisUrl" -}}
{{- $scheme := include "etap-ai.redisScheme" . -}}
{{- $host := include "etap-ai.redisHost" . -}}
{{- $port := include "etap-ai.redisPort" . -}}
{{- $db := include "etap-ai.redisDb" . -}}
{{- if .Values.redis.existingSecret -}}
{{- printf "%s://:$(REDIS_PASSWORD)@%s:%s/%s" $scheme $host $port $db -}}
{{- else -}}
{{- printf "%s://%s:%s/%s" $scheme $host $port $db -}}
{{- end -}}
{{- end -}}

{{/* =========================================================================
   Postgres URL parsing helpers — same pattern as Redis.
   ========================================================================= */}}

{{- define "etap-ai.pgScheme" -}}
{{- if hasPrefix "postgresql://" .Values.database.url -}}postgresql{{- else if hasPrefix "postgres://" .Values.database.url -}}postgres{{- else -}}postgresql{{- end -}}
{{- end -}}

{{- define "etap-ai.pgHostPortDb" -}}
{{- $url := .Values.database.url -}}
{{- $stripped := trimPrefix "postgresql://" $url | trimPrefix "postgres://" -}}
{{- $stripped -}}
{{- end -}}

{{- define "etap-ai.databaseHost" -}}
{{- $s := include "etap-ai.pgHostPortDb" . -}}
{{- $s | trimPrefix "/" | splitList "@" | last | splitList "/" | first | splitList ":" | first -}}
{{- end -}}

{{- define "etap-ai.databasePort" -}}
{{- $s := include "etap-ai.pgHostPortDb" . -}}
{{- $hostport := $s | trimPrefix "/" | splitList "@" | last | splitList "/" | first -}}
{{- $parts := splitList ":" $hostport -}}
{{- if eq (len $parts) 2 -}}{{- index $parts 1 -}}{{- else -}}5432{{- end -}}
{{- end -}}

{{- define "etap-ai.databaseName" -}}
{{- $s := include "etap-ai.pgHostPortDb" . -}}
{{- $parts := splitList "/" $s -}}
{{- if gt (len $parts) 1 -}}{{- index $parts 1 | trimPrefix "?" -}}{{- else -}}etap_db{{- end -}}
{{- end -}}

{{/*
Build DATABASE_URL with $(DATABASE_USER) and $(DATABASE_PASSWORD) placeholders.
Both env vars MUST be defined earlier in the container's env list.
*/}}
{{- define "etap-ai.databaseUrl" -}}
{{- $scheme := include "etap-ai.pgScheme" . -}}
{{- $host := include "etap-ai.databaseHost" . -}}
{{- $port := include "etap-ai.databasePort" . -}}
{{- $db := include "etap-ai.databaseName" . -}}
{{- if .Values.database.existingSecret -}}
{{- printf "%s://$(DATABASE_USER):$(DATABASE_PASSWORD)@%s:%s/%s" $scheme $host $port $db -}}
{{- else -}}
{{- printf "%s://%s:%s/%s" $scheme $host $port $db -}}
{{- end -}}
{{- end -}}

{{/*
Celery broker / result backend default to the redis URL.
*/}}
{{- define "etap-ai.celeryBrokerUrl" -}}
{{- if .Values.env.CELERY_BROKER_URL -}}{{- .Values.env.CELERY_BROKER_URL -}}{{- else -}}{{- include "etap-ai.redisUrl" . -}}{{- end -}}
{{- end -}}

{{- define "etap-ai.celeryResultBackend" -}}
{{- if .Values.env.CELERY_RESULT_BACKEND -}}{{- .Values.env.CELERY_RESULT_BACKEND -}}{{- else -}}{{- include "etap-ai.redisUrl" . -}}{{- end -}}
{{- end -}}
