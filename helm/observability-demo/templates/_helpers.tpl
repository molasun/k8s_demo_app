{{/*
Expand the name of the chart.
*/}}
{{- define "observability-demo.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "observability-demo.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- printf "%s" $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "observability-demo.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "observability-demo.labels" -}}
helm.sh/chart: {{ include "observability-demo.chart" . }}
{{ include "observability-demo.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: observability-demo
{{- end }}

{{/*
Selector labels
*/}}
{{- define "observability-demo.selectorLabels" -}}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Backend labels
*/}}
{{- define "observability-demo.backendLabels" -}}
{{ include "observability-demo.selectorLabels" . }}
app.kubernetes.io/component: backend
{{- end }}

{{/*
Frontend labels
*/}}
{{- define "observability-demo.frontendLabels" -}}
{{ include "observability-demo.selectorLabels" . }}
app.kubernetes.io/component: frontend
{{- end }}

{{/*
OTel Collector endpoint
*/}}
{{- define "observability-demo.otelEndpoint" -}}
{{- .Values.observability.opentelemetry.collectorEndpoint }}
{{- end }}

{{/*
Namespace
*/}}
{{- define "observability-demo.namespace" -}}
{{- default .Release.Namespace .Values.global.namespace }}
{{- end }}
