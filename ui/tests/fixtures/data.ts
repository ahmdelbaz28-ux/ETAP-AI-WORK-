/**
 * Shared E2E fixture data.
 * Centralizes deterministic test identities so specs do not hard-code
 * divergent emails/roles that drift from backend mocks.
 */

export const TEST_USERS = {
  engineer: {
    email: "engineer@etap.com",
    password: "SecurePass123!",
  },
  invalid: {
    email: "bad@example.com",
    password: "wrongpassword",
  },
  generic: {
    email: "test@example.com",
    password: "TestPass123!",
  },
} as const;

export const TEST_ROUTES = {
  public: ["/login", "/register"],
  protectedSample: ["/dashboard", "/studies", "/projects", "/admin"],
} as const;
