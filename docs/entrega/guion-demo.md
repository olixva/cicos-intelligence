# Guion de demo reproducible

1. Mostrar `docs/ESTADO.md`: fuente, edición de 2004 y límites.
2. Arrancar `make local-services-up`, `make serve-backend` y `pnpm --dir frontend dev`.
3. Abrir la UI y consultar la alcoholemia: mostrar evidencia de la página 9; aclarar que daños personales y ámbito penal quedan fuera del Convenio.
4. Probar los cinco relatos del enunciado: distinguir respuesta sustentada, condicionada y abstención. No presentar una conclusión definitiva cuando faltan hechos o la matriz D.A.A.
5. Abrir una cita en el PDF y comprobar página/versión; sin región verificada, sólo navegación a página.
6. Mostrar Langfuse local como observabilidad, no como evaluación concluida.

Contingencias: si OpenAI falla, explicar el error técnico y usar una traza previa sólo identificada como tal; si Qdrant no está listo, mostrar `/health/ready`; si Langfuse falla, la respuesta puede continuar pero no se afirma traza publicada.
