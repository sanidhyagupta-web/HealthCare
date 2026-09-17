---
paths:
  - "tests/**/*.py"
---

# Backend Test Patterns

<!-- CUSTOMIZE: This file describes a two-tier test pattern (service tests + integration tests).
     Code examples below use Java + Spring + Mockito + Testcontainers — adapt to your stack. -->

Two-tier strategy: fast **service tests** (Tier 1, mocked) for business logic + selective **integration tests** (Tier 2, real DB via containers) for API/DB contracts. No in-memory databases — use containers so tests verify the same engine production runs.

## BT-01: Test Configuration <!-- severity: suggestion -->

<!-- CUSTOMIZE: Your test framework setup, profiles, and environment configuration -->

```java
// Java/Spring example — adapt to your stack
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@ActiveProfiles("test")
```

### Security
<!-- CUSTOMIZE: How authentication is handled in tests -->
- A test security config disables real auth in tests
- A test-user annotation provides authenticated requests
- Service-to-service calls mock the client interface only

### Containers (recommended over in-memory)
<!-- CUSTOMIZE: Your test container/DB setup -->
- Real database container (e.g., PostgreSQL via Testcontainers) auto-started via shared base config
- Each test class gets a clean database state
- Migrations run automatically against the test container

### Local Cloud Services (if applicable)
<!-- CUSTOMIZE: If your tests need cloud services (S3, SQS, queues), describe the local emulator setup -->
- Use a local emulator (e.g., LocalStack) when tests interact with cloud APIs
- Document any setup commands developers need to run before tests

## BT-02: Test Structure <!-- severity: suggestion -->

```java
// Java/Spring example — pattern is the same in any framework
@Nested
@DisplayName("POST /api/v1/resource")
class CreateResource {

    @Test
    @DisplayName("should create resource when valid request")
    void shouldCreateResource_WhenValidRequest() {
        // Given — set up data via repositories (NOT mocks)
        // When — call the endpoint
        // Then — assert response and database state
    }
}
```

Group tests by endpoint/feature. Use descriptive names. Follow Given/When/Then.

## BT-03: Key Patterns <!-- severity: blocker -->
- **Data setup**: Insert via real persistence layer, not mocks. Tests verify real DB interactions.
- **External-service mocking**: Mock external client interfaces only. Internal services and repositories use real implementations.
- **Assertions**: Assert HTTP status + response body + DB state via real reads.
- **Cleanup**: Use transactional rollback or explicit cleanup in test teardown.

## BT-04: Running Tests

<!-- CUSTOMIZE: Your project's test invocation commands -->

```bash
# Single test class / file
<your-build-tool> test <test-class-or-file>

# Single method
<your-build-tool> test <test-class>.<method>
```

## BT-05: Service Test Patterns <!-- severity: suggestion -->

Service tests mock the repository layer and test business logic in isolation. Use for all AC scenarios, business rule branches, validation, and edge cases.

```java
// Java/Mockito example — adapt to your stack's mocking library
@ExtendWith(MockitoExtension.class)
class ResourceServiceTest {

    @Mock private ResourceRepository resourceRepository;
    @Mock private ExternalClient externalClient;
    @InjectMocks private ResourceService resourceService;

    @Test
    @DisplayName("should perform action when condition")
    void shouldPerformAction_whenCondition() {
        // Given — set up entity state
        // When — call service method
        // Then — verify state changed and repository.save() called
    }
}
```

### When to use service tests vs integration tests
- **Service tests (Tier 1)**: Business logic, validation rules, state machine transitions, calculations, error handling branches. Every AC scenario. Fast — no DI container or Testcontainers.
- **Integration tests (Tier 2)**: API contracts (endpoint paths, status codes, response shapes), DB contracts (entity persistence, queries, constraints, FK enforcement), auth/security. At least one happy + one error per endpoint, more as ticket ACs demand.
