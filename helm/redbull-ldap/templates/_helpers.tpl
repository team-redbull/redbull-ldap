{{/* Chart name, overridable. */}}
{{- define "redbull-ldap.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/* Fully qualified release name, capped at 63 chars for label limits. */}}
{{- define "redbull-ldap.fullname" -}}
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

{{- define "redbull-ldap.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "redbull-ldap.labels" -}}
helm.sh/chart: {{ include "redbull-ldap.chart" . }}
{{ include "redbull-ldap.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "redbull-ldap.selectorLabels" -}}
app.kubernetes.io/name: {{ include "redbull-ldap.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "redbull-ldap.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "redbull-ldap.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/* The Secret holding AD_API_CLIENT_ID: either one you manage, or ours. */}}
{{- define "redbull-ldap.secretName" -}}
{{- if .Values.secret.existingSecret }}
{{- .Values.secret.existingSecret }}
{{- else }}
{{- include "redbull-ldap.fullname" . }}
{{- end }}
{{- end }}

{{/* The image reference, defaulting the tag to the chart's appVersion. */}}
{{- define "redbull-ldap.image" -}}
{{- printf "%s:%s" .Values.image.repository (default .Chart.AppVersion .Values.image.tag) }}
{{- end }}
