{{/*
Expand the name of the chart.
*/}}
{{- define "rag-valkey.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "rag-valkey.fullname" -}}
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
{{- define "rag-valkey.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "rag-valkey.labels" -}}
helm.sh/chart: {{ include "rag-valkey.chart" . }}
{{ include "rag-valkey.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: advanced-rag
{{- end }}

{{/*
Selector labels
*/}}
{{- define "rag-valkey.selectorLabels" -}}
app.kubernetes.io/name: {{ include "rag-valkey.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Secret name for credentials
*/}}
{{- define "rag-valkey.secretName" -}}
{{- if .Values.auth.existingSecret }}
{{- .Values.auth.existingSecret }}
{{- else }}
{{- include "rag-valkey.fullname" . }}-credentials
{{- end }}
{{- end }}

{{/*
Secret key for password
*/}}
{{- define "rag-valkey.secretKey" -}}
{{- if .Values.auth.existingSecret -}}
{{- .Values.auth.existingSecretPasswordKey -}}
{{- else -}}
password
{{- end -}}
{{- end }}

{{/*
Generate random password if not provided
*/}}
{{- define "rag-valkey.password" -}}
{{- if .Values.auth.password }}
{{- .Values.auth.password }}
{{- else }}
{{- randAlphaNum 24 }}
{{- end }}
{{- end }}
