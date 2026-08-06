---
name: backend-test
description: Write backend tests using a two-tier strategy — service tests for business logic, integration tests for API/DB contracts.
---

# Write Backend Tests

Write tests for a backend service using a two-tier strategy that follows the test pyramid.

> The code examples below use Java + Spring + Mockito + Testcontainers. The **strategy** (Tier 1 mocked service tests + Tier 2 real-DB integration tests) is the same across stacks — adapt the syntax to your project's framework, mocking library, and integration test runner.

## Two-Tier Strategy

### Tier 1 — Service Tests (fast, numerous)

Test business logic in isolation. Mock repositories and feign clients. Cover all acceptance criteria scenarios, business rule branches, validation, edge cases, and error handling.

**When to write:** Every AC scenario, every business logic branch, every validation rule, every error case.

```java
@ExtendWith(MockitoExtension.class)
class OrderServiceTest {

    @Mock private OrderRepository orderRepository;
    @Mock private PaymentClient paymentClient;
    @InjectMocks private OrderService orderService;

    @Nested
    @DisplayName("cancelOrder")
    class CancelOrder {

        @Test
        @DisplayName("should cancel order when status is DRAFT")
        void shouldCancelOrder_whenDraftStatus() {
            // Given — create entity with DRAFT status
            var order = new Order();
            order.setStatus(OrderStatus.DRAFT);
            when(orderRepository.findById(any())).thenReturn(Optional.of(order));

            // When — call service method
            orderService.cancelOrder(orderId, reason);

            // Then — verify status changed, save called
            assertThat(order.getStatus()).isEqualTo(OrderStatus.CANCELLED);
            verify(orderRepository).save(order);
        }

        @Test
        @DisplayName("should throw 409 when already cancelled")
        void shouldThrow409_whenAlreadyCancelled() {
            // Given / When / Then — assert ConflictException
        }
    }
}
```

**Patterns:**
- `@ExtendWith(MockitoExtension.class)` — no Spring context, runs in milliseconds
- `@Mock` for repositories, external clients, and other dependencies
- `@InjectMocks` for the service under test
- Verify both return values and side effects (`verify(repo).save(...)`)
- Use `@Nested` + `@DisplayName` for readability
- Naming: `shouldDoX_whenCondition` format

### Tier 2 — Integration Tests (slower, contract-focused)

Test that layers wire together correctly. Real DB via Testcontainers. Verify API contracts (endpoints, status codes, request/response shapes, auth) and DB contracts (entity persistence, queries, constraints).

**When to write:** At least one happy-path + one error-path per endpoint, more as needed based on ticket ACs and error cases.

```java
@SpringBootTest
@AutoConfigureMockMvc
@Import(TestcontainersConfiguration.class)
@TestPropertySource(properties = {"spring.main.allow-bean-definition-overriding=true"})
@Transactional
class OrderControllerIT {

    @Autowired private MockMvc mockMvc;
    @Autowired private OrderRepository orderRepository;
    @MockBean private PaymentClient paymentClient;

    @Nested
    @DisplayName("PATCH /v1/orders/{id}/cancel")
    class CancelOrder {

        @Test
        @DisplayName("should return 200 and persist CANCELLED status")
        @WithMockJwtUser(authorities = {"orders:write"})
        void shouldCancelOrder_returns200() throws Exception {
            // Given — insert data via repositories
            // When — call the endpoint via MockMvc
            // Then — assert HTTP response AND database state
        }
    }
}
```

**Setup:**
- `@SpringBootTest` + `@AutoConfigureMockMvc` + `@Import(TestcontainersConfiguration.class)`
- `@WithMockJwtUser` for authenticated requests
- `@MockBean` on external client interfaces only — everything else uses real implementations
- Data setup via `@Autowired` repositories (real DB)
- `@Transactional` for auto-rollback after each test

**Patterns:**
- **Data setup**: Always via `@Autowired` repositories against the real DB container
- **External-service mocking**: `@MockBean` on external client interfaces only
- **Assertions**: Assert HTTP status + response body + DB state via repositories
- **Cleanup**: `@Transactional` on class for auto-rollback (preferred) or `@AfterEach`
- **Helper methods**: Extract `createOrderAndCommit()` style helpers for common setup

## Steps

1. Read the service's CLAUDE.md and explore existing test files for patterns
2. Identify acceptance criteria and endpoints to test
3. **Write Tier 1 service tests first** — cover all AC scenarios and logic branches
4. **Write Tier 2 integration tests** — cover API and DB contracts
5. Use `@Nested` groups and `@DisplayName` for readable organization
6. Run tests using your project's test command. <!-- CUSTOMIZE: e.g. `gradle test --tests`, `mvn test -Dtest=`, `pytest`, `go test`, `npm test` -->

## Running

<!-- CUSTOMIZE: Replace with your project's test invocation patterns -->
```bash
# Single test class / file
<your-build-tool> test <test-class-or-file>

# Single method
<your-build-tool> test <test-class>.<method>
```
