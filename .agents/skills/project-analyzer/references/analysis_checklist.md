# Codebase Analysis Checklist

Use this checklist as a standardized evaluation benchmark when auditing codebases:

## 1. Architecture & Modular Organization
- [ ] **Separation of Concerns**: Clear boundaries across Core, Controllers, Services, Repositories, and Models?
- [ ] **Package Management**: Clean package structure with proper `__init__.py` usage for exposed APIs and namespaces?
- [ ] **Naming Conventions**: Conformance with PEP 8 (lowercase module names, snake_case functions/variables, PascalCase classes)?

## 2. Configuration & Security
- [ ] **Secrets Management**: Sensitive values (`SECRET_KEY`, database credentials, API keys) isolated in `.env` and omitted from VCS?
- [ ] **Fail-Fast Validation**: Startup checks for mandatory environment variables?
- [ ] **Password Hashing**: Modern, robust hashing algorithm (Argon2 / Bcrypt) with per-user salt?
- [ ] **Timing Attack Mitigation**: Constant-time comparisons for sensitive tokens and hashes?

## 3. Persistence & Database ORM
- [ ] **Connection Pooling**: Engine and connection pool tuned for concurrency and production load?
- [ ] **Transaction Lifecycle**: Proper session handling and resource cleanup (`try...finally`, dependency injection generators)?
- [ ] **Audit Columns**: Shared timestamp tracking (`created_at`, `updated_at` with UTC timezone)?
- [ ] **Database Migrations**: Integrated versioned schema migration (e.g., Alembic)?

## 4. Performance & Maintainability
- [ ] **Async / Sync Balance**: Proper handling of blocking vs non-blocking I/O operations?
- [ ] **Error Handling**: Centralized exception handlers delivering standardized JSON responses?
- [ ] **Data Validation**: Robust request/response schema validation (Pydantic)?
