# Test Patterns Reference for Spring Boot Verification

This reference covers the three primary testing strategies for Spring Boot applications: unit tests, integration tests, and API tests. Each pattern includes implementation examples, best practices, and common pitfalls.

---

## Table of Contents

1. [Unit Tests](#unit-tests)
2. [Integration Tests with Testcontainers](#integration-tests-with-testcontainers)
3. [API Tests with MockMvc](#api-tests-with-mockmvc)
4. [Test Configuration](#test-configuration)
5. [Test Naming Conventions](#test-naming-conventions)
6. [Common Pitfalls](#common-pitfalls)

---

## Unit Tests

### Purpose

Unit tests verify the behavior of individual classes and methods in isolation. All external dependencies are mocked or stubbed. These tests should be fast (milliseconds), deterministic, and independent of infrastructure.

### When to Use

- Testing service layer business logic
- Testing utility methods and data transformations
- Testing exception handling and edge cases
- Testing conditional logic and branching

### Pattern: Service Layer Test

```java
@ExtendWith(MockitoExtension.class)
class UserServiceTest {

    @Mock
    private UserRepository userRepository;

    @Mock
    private EmailService emailService;

    @InjectMocks
    private UserService userService;

    @Test
    void createUser_validInput_returnsUser() {
        // Arrange
        var dto = new CreateUserDto("Alice", "alice@example.com");
        var expected = new User(1L, "Alice", "alice@example.com");
        when(userRepository.save(any(User.class))).thenReturn(expected);

        // Act
        var result = userService.create(dto);

        // Assert
        assertThat(result.name()).isEqualTo("Alice");
        assertThat(result.email()).isEqualTo("alice@example.com");
        verify(userRepository).save(any(User.class));
        verify(emailService).sendWelcomeEmail(any(User.class));
    }

    @Test
    void createUser_duplicateEmail_throwsException() {
        // Arrange
        var dto = new CreateUserDto("Alice", "existing@example.com");
        when(userRepository.existsByEmail(dto.email())).thenReturn(true);

        // Act & Assert
        assertThatThrownBy(() -> userService.create(dto))
            .isInstanceOf(DuplicateEmailException.class)
            .hasMessageContaining("existing@example.com");

        verify(userRepository, never()).save(any(User.class));
    }

    @Test
    void createUser_invalidName_throwsException() {
        // Arrange
        var dto = new CreateUserDto("", "alice@example.com");

        // Act & Assert
        assertThatThrownBy(() -> userService.create(dto))
            .isInstanceOf(ValidationException.class);
    }

    @Test
    void findUser_existingUser_returnsUser() {
        // Arrange
        var user = new User(1L, "Alice", "alice@example.com");
        when(userRepository.findByEmail("alice@example.com"))
            .thenReturn(Optional.of(user));

        // Act
        var result = userService.findByEmail("alice@example.com");

        // Assert
        assertThat(result).isPresent();
        assertThat(result.get().getName()).isEqualTo("Alice");
    }

    @Test
    void findUser_nonExistentUser_returnsEmpty() {
        // Arrange
        when(userRepository.findByEmail("nobody@example.com"))
            .thenReturn(Optional.empty());

        // Act
        var result = userService.findByEmail("nobody@example.com");

        // Assert
        assertThat(result).isEmpty();
    }
}
```

### Pattern: Utility Class Test

```java
class EmailValidatorTest {

    @ParameterizedTest
    @ValueSource(strings = {
        "user@example.com",
        "user.name@example.com",
        "user+tag@example.co.uk"
    })
    void isValid_validEmails_returnTrue(String email) {
        assertThat(EmailValidator.isValid(email)).isTrue();
    }

    @ParameterizedTest
    @ValueSource(strings = {
        "",
        "not-an-email",
        "@example.com",
        "user@",
        "user@.com"
    })
    void isValid_invalidEmails_returnFalse(String email) {
        assertThat(EmailValidator.isValid(email)).isFalse();
    }

    @Test
    void isValid_nullInput_throwsException() {
        assertThatThrownBy(() -> EmailValidator.isValid(null))
            .isInstanceOf(NullPointerException.class);
    }
}
```

### Pattern: Mapper/Converter Test

```java
@ExtendWith(MockitoExtension.class)
class UserMapperTest {

    @Test
    void toEntity_validDto_returnsEntity() {
        var dto = new CreateUserDto("Alice", "alice@example.com");
        var entity = UserMapper.toEntity(dto);

        assertThat(entity.getName()).isEqualTo("Alice");
        assertThat(entity.getEmail()).isEqualTo("alice@example.com");
        assertThat(entity.getId()).isNull(); // ID not set on creation
    }

    @Test
    void toDto_validEntity_returnsDto() {
        var entity = new User(1L, "Alice", "alice@example.com");
        var dto = UserMapper.toDto(entity);

        assertThat(dto.id()).isEqualTo(1L);
        assertThat(dto.name()).isEqualTo("Alice");
        assertThat(dto.email()).isEqualTo("alice@example.com");
    }

    @Test
    void toDto_nullEntity_throwsException() {
        assertThatThrownBy(() -> UserMapper.toDto(null))
            .isInstanceOf(NullPointerException.class);
    }
}
```

---

## Integration Tests with Testcontainers

### Purpose

Integration tests verify that multiple components work together correctly. They run against real infrastructure (databases, message brokers) using Testcontainers to spin up Docker containers. These tests are slower (seconds) but provide confidence that the application integrates correctly.

### When to Use

- Testing repository layer with real database queries
- Testing transaction boundaries and rollback behavior
- Testing database-specific features (indexes, constraints)
- Testing message broker integration

### Pattern: Repository Integration Test

```java
@SpringBootTest
@Testcontainers
class UserRepositoryIntegrationTest {

    @Container
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:16-alpine")
        .withDatabaseName("testdb")
        .withUsername("test")
        .withPassword("test");

    @DynamicPropertySource
    static void configureProperties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", postgres::getJdbcUrl);
        registry.add("spring.datasource.username", postgres::getUsername);
        registry.add("spring.datasource.password", postgres::getPassword);
        registry.add("spring.jpa.hibernate.ddl-auto", () -> "create-drop");
        registry.add("spring.jpa.show-sql", () -> "true");
    }

    @Autowired
    private UserRepository userRepository;

    @Autowired
    private TestEntityManager entityManager;

    @Test
    void findByEmail_existingUser_returnsUser() {
        var user = new User("Alice", "alice@example.com");
        entityManager.persistAndFlush(user);

        var found = userRepository.findByEmail("alice@example.com");

        assertThat(found).isPresent();
        assertThat(found.get().getName()).isEqualTo("Alice");
    }

    @Test
    void findByEmail_nonExistentUser_returnsEmpty() {
        var found = userRepository.findByEmail("nobody@example.com");

        assertThat(found).isEmpty();
    }

    @Test
    void save_validUser_persistsAndReturnsEntity() {
        var user = new User("Alice", "alice@example.com");
        var saved = userRepository.saveAndFlush(user);

        assertThat(saved.getId()).isNotNull();
        assertThat(saved.getName()).isEqualTo("Alice");

        var fromDb = entityManager.find(User.class, saved.getId());
        assertThat(fromDb).isNotNull();
        assertThat(fromDb.getEmail()).isEqualTo("alice@example.com");
    }

    @Test
    void save_duplicateEmail_throwsConstraintViolation() {
        var user1 = new User("Alice", "alice@example.com");
        var user2 = new User("Bob", "alice@example.com");
        userRepository.saveAndFlush(user1);

        assertThatThrownBy(() -> {
            userRepository.saveAndFlush(user2);
            entityManager.flush();
        }).isInstanceOf(DataIntegrityViolationException.class);
    }

    @Test
    void findAll_returnsAllUsers() {
        entityManager.persist(new User("Alice", "alice@example.com"));
        entityManager.persist(new User("Bob", "bob@example.com"));
        entityManager.flush();

        var users = userRepository.findAll();

        assertThat(users).hasSize(2);
    }
}
```

### Pattern: Service Integration Test

```java
@SpringBootTest
@Testcontainers
class OrderServiceIntegrationTest {

    @Container
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:16-alpine")
        .withDatabaseName("testdb");

    @DynamicPropertySource
    static void configureProperties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", postgres::getJdbcUrl);
        registry.add("spring.datasource.username", postgres::getUsername);
        registry.add("spring.datasource.password", postgres::getPassword);
    }

    @Autowired
    private OrderService orderService;

    @Autowired
    private OrderRepository orderRepository;

    @Autowired
    private ProductRepository productRepository;

    @Test
    void placeOrder_validInput_createsOrderAndUpdatesStock() {
        // Setup
        var product = productRepository.saveAndFlush(
            new Product("Widget", 9.99, 100));

        // Act
        var order = orderService.placeOrder(product.getId(), 5);

        // Assert
        assertThat(order.getId()).isNotNull();
        assertThat(order.getTotal()).isEqualByComparingTo(BigDecimal.valueOf(49.95));

        var updatedProduct = productRepository.findById(product.getId()).orElseThrow();
        assertThat(updatedProduct.getStock()).isEqualTo(95);
    }

    @Test
    void placeOrder_insufficientStock_throwsException() {
        var product = productRepository.saveAndFlush(
            new Product("Widget", 9.99, 3));

        assertThatThrownBy(() -> orderService.placeOrder(product.getId(), 5))
            .isInstanceOf(InsufficientStockException.class);

        // Verify no order was created
        assertThat(orderRepository.count()).isEqualTo(0);
    }
}
```

### Pattern: Kafka Integration Test

```java
@SpringBootTest
@Testcontainers
class KafkaEventConsumerIntegrationTest {

    @Container
    static KafkaContainer kafka = new KafkaContainer(
        DockerImageName.parse("confluentinc/cp-kafka:7.6.0"))
        .withEmbeddedZookeeper();

    @DynamicPropertySource
    static void configureProperties(DynamicPropertyRegistry registry) {
        registry.add("spring.kafka.bootstrap-servers", kafka::getBootstrapServers);
    }

    @Autowired
    private KafkaTemplate<String, String> kafkaTemplate;

    @Autowired
    private EventConsumer eventConsumer;

    @Test
    void consumeEvent_validMessage_processesSuccessfully() throws Exception {
        var message = """
            {"type": "USER_CREATED", "userId": 1, "name": "Alice"}
            """;

        kafkaTemplate.send("user-events", message);

        // Wait for consumer to process
        await().atMost(10, TimeUnit.SECONDS)
            .untilAsserted(() ->
                assertThat(eventConsumer.getProcessedEvents()).hasSize(1));
    }
}
```

---

## API Tests with MockMvc

### Purpose

API tests verify the HTTP layer of the application, including request routing, request/response serialization, validation, and error handling. They use MockMvc to simulate HTTP requests without starting a real server.

### When to Use

- Testing REST controller endpoints
- Testing request validation and error responses
- Testing authentication and authorization
- Testing content negotiation and response formats

### Pattern: CRUD Controller Test

```java
@WebMvcTest(UserController.class)
class UserControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private UserService userService;

    @Autowired
    private ObjectMapper objectMapper;

    @Test
    void createUser_validInput_returns201() throws Exception {
        var user = new UserDto(1L, "Alice", "alice@example.com");
        when(userService.create(any(CreateUserDto.class))).thenReturn(user);

        mockMvc.perform(post("/api/users")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(
                    new CreateUserDto("Alice", "alice@example.com"))))
            .andExpect(status().isCreated())
            .andExpect(jsonPath("$.name").value("Alice"))
            .andExpect(jsonPath("$.email").value("alice@example.com"))
            .andExpect(header().exists("Location"));
    }

    @Test
    void createUser_invalidEmail_returns400() throws Exception {
        mockMvc.perform(post("/api/users")
                .contentType(MediaType.APPLICATION_JSON)
                .content("""
                    {"name": "Alice", "email": "not-an-email"}
                    """))
            .andExpect(status().isBadRequest())
            .andExpect(jsonPath("$.errors").isArray());
    }

    @Test
    void createUser_blankName_returns400() throws Exception {
        mockMvc.perform(post("/api/users")
                .contentType(MediaType.APPLICATION_JSON)
                .content("""
                    {"name": "", "email": "alice@example.com"}
                    """))
            .andExpect(status().isBadRequest());
    }

    @Test
    void getUser_existingUser_returns200() throws Exception {
        var user = new UserDto(1L, "Alice", "alice@example.com");
        when(userService.findById(1L)).thenReturn(Optional.of(user));

        mockMvc.perform(get("/api/users/1"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.name").value("Alice"));
    }

    @Test
    void getUser_nonExistentUser_returns404() throws Exception {
        when(userService.findById(999L)).thenReturn(Optional.empty());

        mockMvc.perform(get("/api/users/999"))
            .andExpect(status().isNotFound());
    }

    @Test
    void listUsers_returns200WithArray() throws Exception {
        var users = List.of(
            new UserDto(1L, "Alice", "alice@example.com"),
            new UserDto(2L, "Bob", "bob@example.com")
        );
        when(userService.findAll()).thenReturn(users);

        mockMvc.perform(get("/api/users"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$").isArray())
            .andExpect(jsonPath("$.length()").value(2));
    }

    @Test
    void deleteUser_existingUser_returns204() throws Exception {
        when(userService.existsById(1L)).thenReturn(true);

        mockMvc.perform(delete("/api/users/1"))
            .andExpect(status().isNoContent());

        verify(userService).deleteById(1L);
    }

    @Test
    void deleteUser_nonExistentUser_returns404() throws Exception {
        when(userService.existsById(999L)).thenReturn(false);

        mockMvc.perform(delete("/api/users/999"))
            .andExpect(status().isNotFound());
    }
}
```

### Pattern: Secured Endpoint Test

```java
@WebMvcTest(AdminController.class)
@Import(SecurityConfig.class)
class AdminControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private UserService userService;

    @Test
    void adminEndpoint_unauthenticated_returns401() throws Exception {
        mockMvc.perform(get("/api/admin/users"))
            .andExpect(status().isUnauthorized());
    }

    @Test
    @WithMockUser(roles = "USER")
    void adminEndpoint_nonAdmin_returns403() throws Exception {
        mockMvc.perform(get("/api/admin/users"))
            .andExpect(status().isForbidden());
    }

    @Test
    @WithMockUser(roles = "ADMIN")
    void adminEndpoint_admin_returns200() throws Exception {
        mockMvc.perform(get("/api/admin/users"))
            .andExpect(status().isOk());
    }
}
```

### Pattern: Exception Handler Test

```java
@WebMvcTest(UserController.class)
class UserControllerExceptionHandlerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private UserService userService;

    @Test
    void createUser_duplicateEmail_returns409() throws Exception {
        when(userService.create(any())).thenThrow(new DuplicateEmailException("exists"));

        mockMvc.perform(post("/api/users")
                .contentType(MediaType.APPLICATION_JSON)
                .content("""
                    {"name": "Alice", "email": "existing@example.com"}
                    """))
            .andExpect(status().isConflict())
            .andExpect(jsonPath("$.error").value("DuplicateEmail"));
    }

    @Test
    void getUser_serviceFailure_returns500() throws Exception {
        when(userService.findById(1L)).thenThrow(new RuntimeException("DB error"));

        mockMvc.perform(get("/api/users/1"))
            .andExpect(status().isInternalServerError());
    }
}
```

---

## Test Configuration

### application-test.yml

```yaml
spring:
  datasource:
    url: jdbc:tc:postgresql:16-alpine:///testdb
    username: test
    password: test
  jpa:
    hibernate:
      ddl-auto: create-drop
    show-sql: false
  main:
    banner-mode: off

logging:
  level:
    root: WARN
    org.springframework.test: DEBUG
```

### Test Configuration Class

```java
@TestConfiguration
public class TestConfig {

    @Bean
    @Primary
    public Clock fixedClock() {
        return Clock.fixed(Instant.parse("2024-01-15T10:30:00Z"), ZoneOffset.UTC);
    }

    @Bean
    @Primary
    public ObjectMapper objectMapper() {
        return new ObjectMapper()
            .registerModule(new JavaTimeModule())
            .disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);
    }
}
```

---

## Test Naming Conventions

| Pattern | Example | File Location |
|---------|---------|---------------|
| `*Test.java` | `UserServiceTest.java` | `src/test/java/` |
| `*Tests.java` | `UserControllerTests.java` | `src/test/java/` |
| `*IT.java` | `UserRepositoryIT.java` | `src/integration-test/java/` |
| `*IntegrationTest.java` | `OrderServiceIntegrationTest.java` | `src/test/java/` |

### Method Naming

```java
// MethodName_StateUnderTest_ExpectedBehavior
void createUser_validInput_returnsUser()
void createUser_duplicateEmail_throwsException()
void findUser_nonExistentUser_returnsEmpty()
```

---

## Common Pitfalls

1. **Testing implementation details** — Test behavior, not implementation. Avoid asserting on private methods or mock interaction counts unless critical.

2. **Over-mocking** — If you mock everything, you are testing the mocks, not the code. Reserve mocking for external dependencies (DB, HTTP, file system).

3. **Shared mutable state** — Tests should be independent. Use `@BeforeEach` to reset state, avoid static mutable fields.

4. **Ignoring test failures** — Never use `@Disabled` without a linked issue ticket. Treat disabled tests as technical debt.

5. **Flaky tests** — Tests that sometimes pass and sometimes fail are worse than no tests. Use `@Retry` sparingly and fix the root cause.

6. **Testcontainers not cleaned up** — Always use `@Container` with `static` fields for shared containers. Use `@Testcontainers(disabledWithoutDocker = true)` to gracefully skip.

7. **AssertJ vs JUnit assertions** — Prefer AssertJ for readability: `assertThat(result).isNotNull()` over `assertNotNull(result)`.

8. **Missing negative test cases** — For every happy path, test at least one error path: invalid input, missing resources, permission denied.
