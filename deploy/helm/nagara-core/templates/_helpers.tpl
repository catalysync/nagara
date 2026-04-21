{{/*
Expand the name of the chart.
*/}}
{{- define "nagara-core.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "nagara-core.fullname" -}}
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

{{- define "nagara-core.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "nagara-core.labels" -}}
helm.sh/chart: {{ include "nagara-core.chart" . }}
{{ include "nagara-core.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "nagara-core.selectorLabels" -}}
app.kubernetes.io/name: {{ include "nagara-core.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "nagara-core.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "nagara-core.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Name of the Secret to consume at runtime — either the user-provided one or
the chart-rendered one.
*/}}
{{- define "nagara-core.secretName" -}}
{{- if .Values.existingSecret -}}
{{ .Values.existingSecret }}
{{- else -}}
{{ include "nagara-core.fullname" . }}
{{- end -}}
{{- end }}

{{- define "nagara-core.image" -}}
{{- $tag := default .Chart.AppVersion .Values.image.tag -}}
{{ printf "%s:%s" .Values.image.repository $tag }}
{{- end }}
