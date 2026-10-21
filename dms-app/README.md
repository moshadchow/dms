# DMS Frontend

React + TypeScript + Vite single-page app for the Document Management System.

---

## Docker

The production image is a two-stage build: Node compiles the Vite bundle, nginx
(unprivileged, `nginxinc/nginx-unprivileged`) serves it and reverse-proxies
`/api` to the FastAPI backend.

```bash
# build (context is this directory)
docker build -t dms-frontend:latest dms-app

# run
docker run -d -p 8080:8080 \
  -e DMS_API_HOST=backend -e DMS_API_PORT=8000 \
  dms-frontend:latest

# or the whole stack
docker compose up --build
```

The bundle is **same-origin** by default: the SPA calls `/api/v1` on its own
host and the nginx layer forwards it to the backend, so there is no CORS and no
backend hostname baked into the JavaScript.

### Build arguments

| Arg | Default | Purpose |
| --- | --- | --- |
| `VITE_API_BASE_URL` | `""` | API root baked into the bundle by Vite. Empty ⇒ same-origin `/api/v1`. Set an absolute URL (`https://api.example.com`) only for a cross-origin API. |
| `VERSION` | `latest` | `org.opencontainers.image.version` label. |
| `VCS_REF` | `""` | `org.opencontainers.image.revision` label. |
| `BUILD_DATE` | `""` | `org.opencontainers.image.created` label. |

### Runtime environment

All of these are read at **container start** — the nginx config is rendered
from `docker/nginx/default.conf.template` by the image's envsubst hook, so a
change needs a restart, never a rebuild.

| Var | Default | Purpose |
| --- | --- | --- |
| `DMS_PORT` | `8080` | Listen port. |
| `DMS_SERVER_NAME` | `_` | `server_name` directive. |
| `DMS_API_HOST` | `backend` | Backend host or IP (resolved at request time). |
| `DMS_API_PORT` | `8000` | Backend port. |
| `DMS_RESOLVER` | `127.0.0.11` | DNS server used to resolve the backend (Docker's embedded DNS). Point it at a real resolver when the backend is addressed by IP or lives outside the Docker network. |
| `DMS_MAX_UPLOAD_MB` | `100` | `client_max_body_size` for `/api` uploads. |
| `DMS_CSP` | see `Dockerfile` | `Content-Security-Policy` value. Widen `connect-src` if the API is cross-origin. |

### Container hardening

The image runs as uid 101 (nginx), listens on 8080 and needs no capabilities.
A fully hardened run looks like this (this is what `docker-compose.yml` does):

```yaml
    read_only: true
    tmpfs:
      - /tmp:rw,noexec,nosuid,size=16m,mode=1777
      - /etc/nginx/conf.d:rw,noexec,nosuid,size=1m,mode=1777
    cap_drop: [ALL]
    security_opt: ["no-new-privileges:true"]
```

`/etc/nginx/conf.d` needs a writable tmpfs because the entrypoint renders the
nginx config there at start-up; `mode=1777` is required for the unprivileged
nginx user to write into it.

### Health

`GET /healthz` returns `200 ok` from nginx itself. The image's `HEALTHCHECK`
uses it, so an API outage does not pull the frontend out of rotation.

---

# React + TypeScript + Vite

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the ESLint configuration

If you are developing a production application, we recommend updating the configuration to enable type-aware lint rules:

```js
export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...

      // Remove tseslint.configs.recommended and replace with this
      tseslint.configs.recommendedTypeChecked,
      // Alternatively, use this for stricter rules
      tseslint.configs.strictTypeChecked,
      // Optionally, add this for stylistic rules
      tseslint.configs.stylisticTypeChecked,

      // Other configs...
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])
```

You can also install [eslint-plugin-react-x](https://github.com/Rel1cx/eslint-react/tree/main/packages/plugins/eslint-plugin-react-x) and [eslint-plugin-react-dom](https://github.com/Rel1cx/eslint-react/tree/main/packages/plugins/eslint-plugin-react-dom) for React-specific lint rules:

```js
// eslint.config.js
import reactX from 'eslint-plugin-react-x'
import reactDom from 'eslint-plugin-react-dom'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...
      // Enable lint rules for React
      reactX.configs['recommended-typescript'],
      // Enable lint rules for React DOM
      reactDom.configs.recommended,
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])
```
