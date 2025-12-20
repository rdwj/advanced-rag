{{/*
Expand the name of the chart.
*/}}
{{- define "rag-vllm-embeddings.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "rag-vllm-embeddings.fullname" -}}
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
{{- define "rag-vllm-embeddings.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "rag-vllm-embeddings.labels" -}}
helm.sh/chart: {{ include "rag-vllm-embeddings.chart" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: advanced-rag
{{- end }}

{{/*
Model-specific labels
*/}}
{{- define "rag-vllm-embeddings.modelLabels" -}}
{{ include "rag-vllm-embeddings.labels" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
PVC name for model cache
*/}}
{{- define "rag-vllm-embeddings.pvcName" -}}
{{- include "rag-vllm-embeddings.fullname" . }}-model-cache
{{- end }}

{{/*
Common environment variables for vLLM containers
*/}}
{{- define "rag-vllm-embeddings.commonEnv" -}}
- name: HOME
  value: /tmp/home
- name: HF_HOME
  value: /models/huggingface
- name: TRANSFORMERS_CACHE
  value: /models/huggingface
- name: VLLM_CACHE_DIR
  value: /models/vllm-cache
- name: XDG_CACHE_HOME
  value: /tmp/cache
{{- end }}

{{/*
Common volume mounts for vLLM containers
*/}}
{{- define "rag-vllm-embeddings.commonVolumeMounts" -}}
- name: model-cache
  mountPath: /models
- name: shm
  mountPath: /dev/shm
- name: tmp-cache
  mountPath: /tmp/cache
- name: tmp-home
  mountPath: /tmp/home
{{- end }}

{{/*
Common volumes for vLLM pods
*/}}
{{- define "rag-vllm-embeddings.commonVolumes" -}}
- name: model-cache
  {{- if .Values.modelCache.enabled }}
  persistentVolumeClaim:
    claimName: {{ include "rag-vllm-embeddings.pvcName" . }}
  {{- else }}
  emptyDir: {}
  {{- end }}
- name: shm
  emptyDir:
    medium: Memory
    sizeLimit: {{ .Values.sharedMemory.size }}
- name: tmp-cache
  emptyDir: {}
- name: tmp-home
  emptyDir: {}
{{- end }}
