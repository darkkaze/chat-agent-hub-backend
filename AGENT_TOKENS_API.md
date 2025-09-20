# Agent Tokens API - Resumen para Frontend

## ⚠️ Importante: Creación automática de tokens

**Al crear un agente se crea automáticamente un token, pero NO se devuelve en el mismo endpoint.**

Cuando llamas a `POST /auth/agents`, se crea:
1. ✅ El agente
2. ✅ Un token asociado al agente automáticamente
3. ❌ **Pero el token NO se incluye en la respuesta**

Para obtener y gestionar los tokens, usa los 3 endpoints específicos descritos abajo.

---

## 🔧 Endpoints para gestión de tokens de agentes

### 1. 📋 Listar tokens activos
```http
GET /auth/agents/{agent_id}/tokens
```

**Propósito:** Obtener todos los tokens activos (no revocados, no expirados) de un agente.

**Autenticación:** Admin requerido

**Response:**
```json
{
  "tokens": [
    {
      "access_token": "tkn_w8kupucc6ungzwkvwg2263ab6mzkzhpq",
      "expires_at": "2026-09-19T22:49:03.577605+00:00"
    }
  ]
}
```

**Casos de uso:**
- Inmediatamente después de crear un agente (para mostrar el token al usuario)
- Consultar tokens existentes para copiar/usar
- Verificar qué tokens están activos

---

### 2. ➕ Crear nuevo token
```http
POST /auth/agents/{agent_id}/tokens
```

**Propósito:** Generar un nuevo token adicional para un agente existente.

**Autenticación:** Admin requerido

**Response:**
```json
{
  "access_token": "tkn_new5fg7h9j2k4l6m8n0p2q4r6s8t0u2",
  "expires_at": "2026-09-20T15:30:00.000000+00:00"
}
```

**Casos de uso:**
- Rotación de tokens por seguridad
- Múltiples tokens para diferentes entornos (dev, prod)
- Recuperación cuando se pierde un token

---

### 3. 🗑️ Revocar token
```http
DELETE /auth/agents/{agent_id}/tokens/{token_id}
```

**Propósito:** Revocar/desactivar un token específico del agente.

**Autenticación:** Admin requerido

**Response:**
```json
{
  "message": "Token tok_abc123 revoked successfully"
}
```

**Notas importantes:**
- ✅ Soft delete: marca `is_revoked = true` (no elimina físicamente)
- ✅ Puede revocar tokens ya revocados sin error
- ✅ Verifica que el token pertenezca al agente especificado

**Casos de uso:**
- Compromiso de seguridad
- Rotación de tokens (revocar el viejo después de crear uno nuevo)
- Gestión de tokens múltiples

---

## 🚀 Flujo recomendado para frontend

### Al crear un agente:
1. **Frontend:** `POST /auth/agents` → Crea agente
2. **Frontend:** `GET /auth/agents/{id}/tokens` → Obtiene token automático
3. **Frontend:** Muestra modal con token para copiar

### Para gestión posterior:
- **Listar:** `GET /auth/agents/{id}/tokens` para ver tokens activos
- **Crear:** `POST /auth/agents/{id}/tokens` para generar nuevos
- **Revocar:** `DELETE /auth/agents/{id}/tokens/{token_id}` para desactivar

### Codes de error comunes:
- **401:** No autenticado
- **403:** Usuario no es admin
- **404:** Agente no encontrado O token no encontrado/no pertenece al agente

---

## 💡 Notas para implementación

**Token Format:** Todos los tokens inician con `tkn_` seguido de 32 caracteres aleatorios.

**Expiración:** Los tokens de agente expiran en 1 año desde su creación.

**Múltiples tokens:** Un agente puede tener múltiples tokens activos simultáneamente.

**Seguridad:** Solo usuarios admin pueden gestionar tokens de agentes.

**Uso del token:** Incluir en headers de requests:
```
Authorization: Bearer tkn_w8kupucc6ungzwkvwg2263ab6mzkzhpq
```