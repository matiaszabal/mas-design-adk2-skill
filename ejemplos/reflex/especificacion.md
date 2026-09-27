# Especificación — Reflex (enrutamiento de mensajes en un banco ficticio)

Instancia de `../../references/plantilla_especificacion.md`.

## 1. Objetivo y alcance

- **Problema:** clasificar mensajes entrantes de clientes y enviarlos a la cola correcta (tarjetas, préstamos, fraude), derivando a una persona todo lo que no se pueda clasificar con seguridad.
- **Arquetipo:** Reflex: alto volumen, decisión de una sola pasada, acción barata y reversible (poner un caso en una cola).
- **Por qué no uno más simple / más complejo:** no hay nada más simple; no hace falta buscar información ni varios pasos.
- **Datos:** mensajes sintéticos.

## 2. Las tres decisiones

- **¿Quién decide qué sigue?** Nadie decide en ejecución: el flujo es de un solo paso. La «decisión» es una **regla** (código) o **una única inferencia** del modelo. El código convierte (intención, confianza) en una ruta.
- **¿Con qué contexto?** Solo la percepción actual (el mensaje), con `include_contents="none"`.
- **¿Cuándo se detiene?** Al llegar a una cola. No hay condición de corte porque no hay iteración. **Escape:** baja/media confianza, intención «otro» o una ruta inesperada → `DEFAULT_ROUTE` → una persona.

## 3. Criterios de aceptación

1. Cada intención inequívoca va a su cola con **una sola** llamada al modelo y **un solo** contenido.
2. Lo no clasificable con seguridad va a un humano.
3. Una ruta inesperada no se pierde (hay ruta por defecto).
4. La variante por reglas usa 0 llamadas al modelo y tiene el mismo escape.
5. Con Gemini real: los mensajes inequívocos van a su cola y los ambiguos o fuera de alcance, a un humano.

## 4. Restricciones

- Sin datos reales. La cola de fraude tiene prioridad alta: **un mensaje no debería poder elegir su propia prioridad** (ver la prueba de inyección en `revision.md`).
