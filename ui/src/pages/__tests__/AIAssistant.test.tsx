/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import AIAssistant from '../AIAssistant';
import { NotificationProvider } from '../../context/NotificationContext';

// ── Mocks ──────────────────────────────────────────────────────────────────────

const mockFetchAgents = vi.fn();
const mockChatWithAgent = vi.fn();

vi.mock('../../lib/api', () => ({
  fetchAgents: (...args: unknown[]) => mockFetchAgents(...args),
  chatWithAgent: (...args: unknown[]) => mockChatWithAgent(...args),
}));

vi.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
      <div {...props}>{children}</div>
    ),
  },
  AnimatePresence: ({ children }: React.PropsWithChildren) => <>{children}</>,
}));

// ── Helpers ────────────────────────────────────────────────────────────────────

const mockAgents = [
  {
    id: 'power-system-coordinator-agent',
    name: 'Power System Coordinator',
    description: 'Main coordinator agent',
    capabilities: ['load_flow', 'short_circuit', 'arc_flash'],
    model: 'gpt-4o-mini',
    provider: 'openai',
  },
  {
    id: 'protection-agent',
    name: 'Protection Agent',
    description: 'Relay coordination agent',
    capabilities: ['protection_coordination'],
    model: 'gpt-4o',
    provider: 'openai',
  },
];

function renderAssistant() {
  return render(
    <NotificationProvider>
      <AIAssistant />
    </NotificationProvider>,
  );
}

// ── Tests ──────────────────────────────────────────────────────────────────────

describe('AIAssistant', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Mock scrollIntoView which is not available in jsdom
    Element.prototype.scrollIntoView = vi.fn();
    mockFetchAgents.mockResolvedValue(mockAgents);
    mockChatWithAgent.mockResolvedValue({
      response: 'Here is the load flow analysis result.',
      agentId: 'power-system-coordinator-agent',
    });
  });

  it('renders the page title and empty-state prompt', async () => {
    renderAssistant();
    expect(screen.getByText('AI Assistant')).toBeTruthy();
    expect(screen.getByText('Start a Conversation')).toBeTruthy();
    expect(screen.getByText(/Ask about power systems analysis/)).toBeTruthy();
  });

  it('loads and displays agents in the dropdown', async () => {
    renderAssistant();
    await waitFor(() => expect(mockFetchAgents).toHaveBeenCalledOnce());
    const select = screen.getByRole('combobox');
    expect(select).toBeTruthy();
    const options = select.querySelectorAll('option');
    expect(options).toHaveLength(2);
    expect(options[0].textContent).toBe('Power System Coordinator');
    expect(options[1].textContent).toBe('Protection Agent');
  });

  it('shows agent info bar after agents load', async () => {
    renderAssistant();
    await waitFor(() => expect(mockFetchAgents).toHaveBeenCalledOnce());
    // Agent name appears in both the dropdown and the info bar, use getAllByText
    const agentNames = screen.getAllByText('Power System Coordinator');
    expect(agentNames.length).toBeGreaterThanOrEqual(2); // dropdown option + info bar
    expect(screen.getByText(/load_flow/)).toBeTruthy();
    expect(screen.getByText('openai')).toBeTruthy();
  });

  it('sends a message and receives a reply', async () => {
    const user = userEvent.setup();
    renderAssistant();
    await waitFor(() => expect(mockFetchAgents).toHaveBeenCalledOnce());

    const input = screen.getByPlaceholderText(/Ask about power systems engineering/);
    await user.type(input, 'Run a load flow analysis');
    const form = input.closest('form')!;
    await user.click(form.querySelector('button[type="submit"]')!);

    await waitFor(() => {
      expect(screen.getByText('Run a load flow analysis')).toBeTruthy();
    });

    await waitFor(() => {
      expect(mockChatWithAgent).toHaveBeenCalledWith(
        'power-system-coordinator-agent',
        expect.stringContaining('Run a load flow analysis'),
      );
    });

    await waitFor(() => {
      expect(screen.getByText('Here is the load flow analysis result.')).toBeTruthy();
    });
  });

  it('shows error notification when chat fails', async () => {
    const user = userEvent.setup();
    mockChatWithAgent.mockRejectedValue(new Error('Network error'));
    renderAssistant();
    await waitFor(() => expect(mockFetchAgents).toHaveBeenCalledOnce());

    const input = screen.getByPlaceholderText(/Ask about power systems engineering/);
    await user.type(input, 'Hello');
    const form = input.closest('form')!;
    await user.click(form.querySelector('button[type="submit"]')!);

    await waitFor(() => {
      expect(mockChatWithAgent).toHaveBeenCalled();
    });

    await waitFor(() => {
      expect(screen.getByText('Hello')).toBeTruthy();
    });
  });

  it('clears conversation when Clear button is clicked', async () => {
    const user = userEvent.setup();
    renderAssistant();
    await waitFor(() => expect(mockFetchAgents).toHaveBeenCalledOnce());

    const input = screen.getByPlaceholderText(/Ask about power systems engineering/);
    await user.type(input, 'Test message');
    const form = input.closest('form')!;
    await user.click(form.querySelector('button[type="submit"]')!);

    await waitFor(() => {
      expect(screen.getByText('Test message')).toBeTruthy();
    });

    const clearBtn = screen.getByText('Clear');
    await user.click(clearBtn);

    await waitFor(() => {
      expect(screen.getByText('Start a Conversation')).toBeTruthy();
    });
  });

  it('does not send empty messages', async () => {
    const user = userEvent.setup();
    renderAssistant();
    await waitFor(() => expect(mockFetchAgents).toHaveBeenCalledOnce());

    const submitBtn = document.querySelector('button[type="submit"]') as HTMLButtonElement;
    expect(submitBtn.disabled).toBe(true);

    const input = screen.getByPlaceholderText(/Ask about power systems engineering/);
    await user.type(input, '   ');

    expect(mockChatWithAgent).not.toHaveBeenCalled();
  });

  it('populates input when quick-prompt button is clicked', async () => {
    const user = userEvent.setup();
    renderAssistant();
    await waitFor(() => expect(mockFetchAgents).toHaveBeenCalledOnce());

    const quickBtn = screen.getByText('Run a load flow analysis');
    await user.click(quickBtn);

    const input = screen.getByPlaceholderText(
      /Ask about power systems engineering/,
    ) as HTMLInputElement;
    expect(input.value).toBe('Run a load flow analysis');
  });
});
