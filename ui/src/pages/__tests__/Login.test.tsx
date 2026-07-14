import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
/**
 * @vitest-environment jsdom
 *
 * Tests for the Login page component (Arabic UI version).
 *
 * The login page now renders in Arabic (RTL). Test selectors updated to
 * match Arabic text: "البريد الإلكتروني" (Email), "كلمة المرور" (Password),
 * "تسجيل الدخول" (Sign in heading), "دخول" (Sign in button), etc.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../../hooks/useAuth";
import Login from "../Login";

// ── Mocks ──
const mockLogin = vi.fn();

vi.mock("../../hooks/useAuth", async () => {
  const actual = await vi.importActual<typeof import("../../hooks/useAuth")>("../../hooks/useAuth");
  return {
    ...actual,
    useAuth: () => ({
      user: null,
      isAuthenticated: false,
      isLoading: false,
      login: mockLogin,
      logout: vi.fn(),
      register: vi.fn(),
      refreshToken: vi.fn(),
    }),
  };
});

const mockNavigate = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

const mockChangeLanguage = vi.fn();
const mockT = vi.fn((key: string) => {
  const map: Record<string, string> = {
    "auth.emailLabel": "البريد الإلكتروني",
    "auth.emailPlaceholder": "name@company.com",
    "auth.passwordLabel": "كلمة المرور",
    "auth.passwordPlaceholder": "••••••••",
    "auth.loginTitle": "تسجيل الدخول",
    "auth.loginSubtitle": "أدخل بياناتك للمتابعة",
    "auth.loginButton": "دخول",
    "auth.loggingIn": "جارٍ تسجيل الدخول",
    "auth.registerLink": "أنشئ واحداً",
    "auth.welcomeBack": "مرحباً بعودتك!",
    "auth.loginFailed": "فشل تسجيل الدخول",
    "auth.instructionsSent": "تم إرسال التعليمات",
    "auth.cancel": "إلغاء",
  };
  return map[key] || key;
});

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: mockT,
    i18n: {
      language: "ar",
      changeLanguage: mockChangeLanguage,
    },
  }),
}));

// ── Helpers ──

function renderLogin() {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <Login />
      </AuthProvider>
    </MemoryRouter>,
  );
}

// ── Tests ──

describe("Login", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useRealTimers();
    mockFetch.mockResolvedValue({
      ok: false,
      json: () => Promise.resolve({ detail: "Not authenticated" }),
    });
  });

  it("renders the login form with email and password fields", () => {
    renderLogin();
    // Arabic label: البريد الإلكتروني = Email
    expect(screen.getByText(/البريد الإلكتروني/i)).toBeTruthy();
    expect(screen.getByPlaceholderText(/^•+$/)).toBeTruthy();
    expect(screen.getByRole("button", { name: /دخول/i })).toBeTruthy();
  });

  it("renders the credentials heading", () => {
    renderLogin();
    // Arabic: أدخل بياناتك للمتابعة
    expect(screen.getByText(/أدخل بياناتك للمتابعة/i)).toBeTruthy();
  });

  it("does NOT render any Demo Mode banner", () => {
    renderLogin();
    expect(screen.queryByText(/Demo Mode Active/i)).toBeNull();
    expect(screen.queryByText(/Demo Build/i)).toBeNull();
    const emailInput = screen.getByRole("textbox") as HTMLInputElement;
    const passwordInput = screen.getByPlaceholderText(/^•+$/) as HTMLInputElement;
    expect(emailInput.value).toBe("");
    expect(passwordInput.value).toBe("");
  });

  it("shows validation error when submitting empty required fields", async () => {
    const user = userEvent.setup();
    renderLogin();
    const submitBtn = screen.getByRole("button", { name: /دخول/i });
    await user.click(submitBtn);
    expect(mockLogin).not.toHaveBeenCalled();
  });

  it("calls useAuth().login and navigates on successful backend auth", async () => {
    // First call: POST /login returns tokens
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          access_token: "test-access-token",
          refresh_token: "test-refresh-token",
        }),
    });
    // Second call: GET /me returns user profile
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({ id: "1", email: "engineer@etap.com", name: "Engineer", role: "admin" }),
    });

    const user = userEvent.setup();
    renderLogin();

    const emailInput = screen.getByRole("textbox") as HTMLInputElement;
    const passwordInput = screen.getByPlaceholderText(/^•+$/) as HTMLInputElement;
    await user.type(emailInput, "engineer@etap.com");
    await user.type(passwordInput, "password123");

    const submitBtn = screen.getByRole("button", { name: /دخول/i });
    await user.click(submitBtn);

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith("engineer@etap.com", "password123");
    });
    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith("/dashboard", { replace: true });
    });
  });

  it("shows error message in red banner when backend rejects with auth error", async () => {
    mockLogin.mockRejectedValue(new Error("Invalid credentials"));
    const user = userEvent.setup();
    renderLogin();

    const emailInput = screen.getByRole("textbox") as HTMLInputElement;
    const passwordInput = screen.getByPlaceholderText(/^•+$/) as HTMLInputElement;
    await user.type(emailInput, "bad@example.com");
    await user.type(passwordInput, "wrongpassword");

    const submitBtn = screen.getByRole("button", { name: /دخول/i });
    await user.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText("Invalid credentials")).toBeTruthy();
    });
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it("shows error message when backend is unreachable (network error) — NO demo fallback", async () => {
    mockLogin.mockRejectedValue(new Error("Failed to fetch"));
    const user = userEvent.setup();
    renderLogin();

    const emailInput = screen.getByRole("textbox") as HTMLInputElement;
    const passwordInput = screen.getByPlaceholderText(/^•+$/) as HTMLInputElement;
    await user.type(emailInput, "test@example.com");
    await user.type(passwordInput, "password123");

    const submitBtn = screen.getByRole("button", { name: /دخول/i });
    await user.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText("Failed to fetch")).toBeTruthy();
    });
    expect(localStorage.getItem("authToken")).toBeNull();
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it("shows loading state during login submission", async () => {
    mockLogin.mockReturnValue(new Promise(() => {}));
    const user = userEvent.setup();
    renderLogin();

    const emailInput = screen.getByRole("textbox") as HTMLInputElement;
    const passwordInput = screen.getByPlaceholderText(/^•+$/) as HTMLInputElement;
    await user.type(emailInput, "test@etap.com");
    await user.type(passwordInput, "password123");

    const submitBtn = screen.getByRole("button", { name: /دخول/i });
    await user.click(submitBtn);

    await waitFor(() => {
      // Arabic: جارٍ تسجيل الدخول... = Signing in...
      expect(screen.getByText(/جارٍ تسجيل الدخول/i)).toBeTruthy();
    });
  });

  it("has a link to the registration page", () => {
    renderLogin();
    // Arabic: أنشئ واحداً = Create one
    const signUpLink = screen.getByText("أنشئ واحداً");
    expect(signUpLink).toBeTruthy();
    expect(signUpLink.closest("a")?.getAttribute("href")).toBe("/register");
  });

  it("has proper input types for email and password", () => {
    renderLogin();
    const emailInput = screen.getByRole("textbox") as HTMLInputElement;
    const passwordInput = screen.getByPlaceholderText(/^•+$/) as HTMLInputElement;
    expect(emailInput.type).toBe("email");
    expect(passwordInput.type).toBe("password");
  });

  it("toggles language when clicking the language switcher button", async () => {
    const user = userEvent.setup();
    renderLogin();

    // Find the language toggle button. Since our mock sets language to 'ar',
    // the button should show 'English' to allow switching back.
    const langBtn = screen.getByRole("button", { name: /English/i });
    expect(langBtn).toBeTruthy();

    // Click the button
    await user.click(langBtn);

    // Verify that changeLanguage was called to switch language
    expect(mockChangeLanguage).toHaveBeenCalledWith("en");
  });
});
