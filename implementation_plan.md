# Mejora Integral del Proyecto ASV Kit

Sistema de domótica asistiva para personas con discapacidad auditiva. El proyecto tiene un backend Flask + SQLite y un frontend multi-página con landing, login, dashboard y páginas CRUD. Ya tiene buenas bases visuales; esta mejora lo llevará al siguiente nivel.

## Resumen de Mejoras

### 🔧 Backend (app.py, models.py, database.py)

| Área | Problema actual | Mejora |
|------|----------------|--------|
| Seguridad | Secret key hardcodeada | Usar `os.environ` con fallback |
| Seguridad | Registro abierto sin restricción | Proteger `/api/auth/register` con `@login_required @admin_required` |
| Bug | Import duplicado de `UserMixin` en models.py (línea 2 y línea 50) | Eliminar import duplicado |
| API | Sin endpoint de estadísticas (dashboard hace 2 requests) | Agregar `/api/stats` que devuelve conteo resumido |
| API | Sin endpoint para actualizar usuarios | Agregar `PUT /api/users/<id>` para toggle active/cambio de rol |
| API | Sin paginación en alertas | Agregar paginación con `?page=&per_page=` |
| Robustez | Sin manejo de errores de JSON | Agregar validación con `try/except` en endpoints |
| Robustez | Sin logging | Agregar logging básico |

---

### 🎨 Frontend — Landing Page (index.html)

| Área | Mejora |
|------|--------|
| Visual | Agregar sección de **testimonios/accesibilidad** con animación |
| Visual | Agregar **favicon** y **Open Graph meta tags** |
| Visual | Mejorar responsive del nav con **hamburger menu** para mobile |
| Interacción | Agregar **smooth parallax** al hero con gradientes |
| Animación | Agregar **typing effect** al hero subtitle |
| Performance | Agregar `loading="lazy"` y optimización del canvas para mobile (reducir partículas) |

---

### 🎨 Frontend — Panel (dashboard, historial, sensores, dispositivos, usuarios)

| Área | Mejora |
|------|--------|
| **DRY** | Extraer sidebar, topbar, auth-check y utils a un `shared.js` compartido |
| **Dashboard** | Agregar **gráfico de alertas** por día (últimos 7 días) usando canvas puro |
| **Dashboard** | Agregar **mapa de calor** por tipo de sensor (mini chart) |
| **Dashboard** | Responsive: grid 2 columnas → 1 columna en mobile |
| **Historial** | Agregar **paginación** frontend con botones |
| **Historial** | Agregar **export a CSV** |
| **Login** | Agregar **animación** al fondo con mesh animado |
| **Login** | Mejorar feedback con **shake animation** en error |
| **Todas** | Agregar **mobile sidebar toggle** (hamburger) |
| **Todas** | Agregar **breadcrumbs** en el topbar |
| **Todas** | Agregar **skeleton loaders** en vez de "Cargando..." |
| **Todas** | Agregar **confirmación mejorada** (modal custom en vez de `confirm()`) |
| **Style.css** | Agregar **scroll-to-top** micro-animation |
| **Style.css** | Mejorar **hover states** de tabs y botones |
| **Style.css** | Agregar **responsive sidebar** que se colapsa en mobile |

---

## Proposed Changes

### Backend

#### [MODIFY] [models.py](file:///c:/xampp/htdocs/asvkit/backend/models.py)
- Eliminar import duplicado de `UserMixin` en línea 50
- Agregar campo `last_login` a `User`

#### [MODIFY] [app.py](file:///c:/xampp/htdocs/asvkit/backend/app.py)
- Proteger endpoint de registro con `admin_required`
- Agregar `/api/stats` endpoint con conteos de alertas/sensores/dispositivos
- Agregar paginación en `/api/alerts`
- Agregar `PUT /api/users/<id>` para toggle active
- Agregar endpoint `/api/alerts/chart` con datos agrupados por día (últimos 7 días)
- Mejorar manejo de errores con `try/except`
- Usar env var para secret key
- Agregar logging
- Actualizar `last_login` en el login

#### [MODIFY] [database.py](file:///c:/xampp/htdocs/asvkit/backend/database.py)
- Sin cambios significativos (funciona bien)

---

### Frontend

#### [MODIFY] [style.css](file:///c:/xampp/htdocs/asvkit/frontend/style.css)
- Agregar estilos para mobile sidebar toggle
- Agregar skeleton loader CSS
- Agregar breadcrumb styles
- Agregar mini chart styles
- Mejorar hover states, gradientes y transiciones
- Agregar confirmación modal mejorada
- Agregar responsive breakpoints para sidebar

#### [NEW] [shared.js](file:///c:/xampp/htdocs/asvkit/frontend/shared.js)
- Extraer: `API` constant, `authCheck()`, `initSidebar()`, `logout()`, `showToast()`, `timeAgo()`, `TYPE` mapping
- Mobile sidebar toggle logic
- Breadcrumb renderer

#### [MODIFY] [index.html](file:///c:/xampp/htdocs/asvkit/frontend/index.html)
- Agregar Open Graph meta tags y favicon placeholder
- Agregar hamburger menu móvil en nav
- Agregar sección de testimonios/accesibilidad
- Optimizar canvas para mobile
- Agregar scroll indicator en hero

#### [MODIFY] [login.html](file:///c:/xampp/htdocs/asvkit/frontend/login.html)
- Agregar animated mesh background
- Agregar shake animation en error
- Agregar indicador de carga en botón (spinner)
- Mejorar UX con auto-focus

#### [MODIFY] [dashboard.html](file:///c:/xampp/htdocs/asvkit/frontend/dashboard.html)
- Usar `shared.js`
- Agregar gráfico de alertas últimos 7 días (canvas chart)
- Agregar responsive layout
- Agregar skeleton loaders
- Agregar mobile sidebar

#### [MODIFY] [historial.html](file:///c:/xampp/htdocs/asvkit/frontend/historial.html)
- Usar `shared.js`
- Agregar paginación frontend
- Agregar botón "Exportar CSV"
- Agregar skeleton loaders

#### [MODIFY] [sensores.html](file:///c:/xampp/htdocs/asvkit/frontend/sensores.html)
- Usar `shared.js`
- Agregar skeleton loaders
- Agregar search/filter inline

#### [MODIFY] [dispositivos.html](file:///c:/xampp/htdocs/asvkit/frontend/dispositivos.html)
- Usar `shared.js`
- Agregar skeleton loaders

#### [MODIFY] [usuarios.html](file:///c:/xampp/htdocs/asvkit/frontend/usuarios.html)
- Usar `shared.js`
- Agregar toggle de estado activo/inactivo
- Agregar skeleton loaders

---

## Verification Plan

### Manual Verification
- Iniciar el servidor Flask y verificar que todos los endpoints respondan
- Navegar por todas las páginas del panel y verificar funcionalidad
- Probar login/logout
- Probar CRUD de sensores, dispositivos y usuarios
- Verificar responsive en diferentes tamaños de pantalla
- Verificar la landing page y sus animaciones
