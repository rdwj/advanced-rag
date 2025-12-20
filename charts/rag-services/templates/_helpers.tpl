{{/*
Expand the name of the chart.
*/}}
{{- define "rag-services.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "rag-services.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "rag-services.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "rag-services.labels" -}}
helm.sh/chart: {{ include "rag-services.chart" . }}
{{ include "rag-services.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "rag-services.selectorLabels" -}}
app.kubernetes.io/name: {{ include "rag-services.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Service-specific labels
*/}}
{{- define "rag-services.serviceLabels" -}}
{{ include "rag-services.labels" . }}
app.kubernetes.io/part-of: advanced-rag
{{- end }}

{{/*
Generate image reference based on registry configuration
*/}}
{{- define "rag-services.image" -}}
{{- $image := .image -}}
{{- $tag := .tag -}}
{{- $namespace := .namespace -}}
{{- if .internal -}}
image-registry.openshift-image-registry.svc:5000/{{ $namespace }}/{{ $image }}:{{ $tag }}
{{- else -}}
{{ .external }}/{{ $image }}:{{ $tag }}
{{- end -}}
{{- end }}

{{/*
Common security context for all pods
*/}}
{{- define "rag-services.securityContext" -}}
runAsNonRoot: true
seccompProfile:
  type: RuntimeDefault
{{- end }}

{{/*
Common container security context
*/}}
{{- define "rag-services.containerSecurityContext" -}}
allowPrivilegeEscalation: false
capabilities:
  drop:
    - ALL
{{- end }}
