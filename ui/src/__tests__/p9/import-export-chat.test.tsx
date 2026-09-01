import "@testing-library/jest-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ResultCard } from "../../components/cards/ResultCard";
import { MessageInput } from "../../components/chat/MessageInput";
import { useChatStore, type ResultEntry } from "../../store/chatStore";

describe("P9: Import / Export in Chat Components", () => {
  beforeEach(() => {
    useChatStore.getState().clearSessionData();
  });

  describe("ResultCard", () => {
    it("renders data import results with buses and branches metrics", () => {
      const entry: ResultEntry = {
        resultId: "res_imp_1234567890abcdef",
        tool: "data_import",
        summary: {
          filename: "substation_alpha.json",
          format: "json",
          records_imported: 42,
          buses_count: 24,
          branches_count: 18,
        },
      };

      render(<ResultCard result={entry} />);

      expect(screen.getByText("Data Import Result")).toBeInTheDocument();
      expect(screen.getByText("substation_alpha.json")).toBeInTheDocument();
      expect(screen.getByText("42")).toBeInTheDocument();
      expect(screen.getByText("24")).toBeInTheDocument();
      expect(screen.getByText("18")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /view result/i })).toBeInTheDocument();
    });

    it("renders data export results safely", () => {
      const entry: ResultEntry = {
        resultId: "res_exp_1234567890abcdef",
        tool: "data_export",
        summary: {
          file_name: "grid_study_report.pdf",
          export_type: "pdf",
          file_size_bytes: 1048576,
        },
      };

      render(<ResultCard result={entry} />);

      expect(screen.getByText("Data Export Result")).toBeInTheDocument();
      expect(screen.getByText("grid_study_report.pdf")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /view result/i })).toBeInTheDocument();
    });

    it("escapes malicious filename and prevents XSS", () => {
      const maliciousName = '<img src=x onerror="alert(1)">evil.json';
      const entry: ResultEntry = {
        resultId: "res_xss_test_12345678",
        tool: "data_import",
        summary: {
          filename: maliciousName,
          format: "json",
        },
      };

      const { container } = render(<ResultCard result={entry} />);
      expect(container.querySelector("img")).toBeNull();
      expect(screen.getByText(maliciousName)).toBeInTheDocument();
    });

    it("triggers selectResult on click", async () => {
      const user = userEvent.setup();
      const entry: ResultEntry = {
        resultId: "res_click_test_1234567",
        tool: "load_flow",
      };

      render(<ResultCard result={entry} />);
      const btn = screen.getByTestId("open-result-res_click_test_1234567");
      await user.click(btn);

      expect(useChatStore.getState().selectedResultId).toBe("res_click_test_1234567");
    });
  });

  describe("MessageInput", () => {
    it("attachments button is hidden by default (fail-closed)", () => {
      render(<MessageInput />);
      expect(screen.queryByTestId("attach-file-btn")).toBeNull();
    });

    it("shows attachment button when attachmentsEnabled is true", () => {
      render(<MessageInput attachmentsEnabled={true} />);
      expect(screen.getByTestId("attach-file-btn")).toBeInTheDocument();
    });

    it("rejects oversized file > 10 MiB", () => {
      render(<MessageInput attachmentsEnabled={true} />);
      const input = screen.getByTestId("chat-file-input") as HTMLInputElement;

      const oversizedFile = new File([new Uint8Array(11 * 1024 * 1024)], "large.json", {
        type: "application/json",
      });

      fireEvent.change(input, { target: { files: [oversizedFile] } });

      expect(screen.getByText(/exceeds maximum allowed size of 10 MB/i)).toBeInTheDocument();
      expect(screen.queryByText("large.json")).toBeNull();
    });

    it("rejects unsupported file extension", () => {
      render(<MessageInput attachmentsEnabled={true} />);
      const input = screen.getByTestId("chat-file-input") as HTMLInputElement;

      const badFile = new File([new Uint8Array(100)], "malicious.exe", {
        type: "application/x-msdownload",
      });

      fireEvent.change(input, { target: { files: [badFile] } });

      expect(screen.getByText(/Unsupported file type/i)).toBeInTheDocument();
    });

    it("accepts valid power-system file and attaches to message", async () => {
      const user = userEvent.setup();
      const onSend = vi.fn().mockResolvedValue(true);
      render(<MessageInput attachmentsEnabled={true} onSend={onSend} />);

      const input = screen.getByTestId("chat-file-input") as HTMLInputElement;
      const validFile = new File([new Uint8Array(2048)], "network_model.raw", {
        type: "text/plain",
      });

      fireEvent.change(input, { target: { files: [validFile] } });

      expect(screen.getByText("network_model.raw")).toBeInTheDocument();

      const textarea = screen.getByLabelText("Chat message");
      await user.type(textarea, "Please import this network");

      const sendBtn = screen.getByRole("button", { name: /send/i });
      await user.click(sendBtn);

      expect(onSend).toHaveBeenCalledWith("Please import this network [Attached: network_model.raw]");
    });

    it("preserves draft on send failure", async () => {
      const user = userEvent.setup();
      const onSend = vi.fn().mockResolvedValue(false);
      render(<MessageInput onSend={onSend} />);

      const textarea = screen.getByLabelText("Chat message") as HTMLTextAreaElement;
      await user.type(textarea, "Critical unsaved draft");

      const sendBtn = screen.getByRole("button", { name: /send/i });
      await user.click(sendBtn);

      expect(textarea.value).toBe("Critical unsaved draft");
    });
  });
});
