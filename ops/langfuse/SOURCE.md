# Langfuse Compose source

`compose.upstream.yaml` is an unmodified snapshot of Langfuse's official self-hosted
Docker Compose file at commit
`fbd612a200e3e4c95426b792857922372b7f6445`.

- Repository: <https://github.com/langfuse/langfuse>
- Source path: `docker-compose.yml`
- Commit: `fbd612a200e3e4c95426b792857922372b7f6445`
- Snapshot SHA-256: `fb70bd8efc15c38eeaf0ae1077af97f9c7f3fca33f57ee72cc42137d0b503814`
- Observed server release from the pinned image: `4.26.0`

The root `compose.yaml` is the resolved project configuration for local use. It retains
the upstream dependencies while replacing all images with measured immutable digests,
binding published ports to loopback, loading project-specific secrets from the ignored
`ops/local.env`, and disabling telemetry and optional cloud-backed AI-agent settings.
