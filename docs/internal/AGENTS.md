# Agent Development Guidelines

## Project Overview

**Goal:** PLAN TO BUILD A SMART AGENT 

**Framework:** Mastra
**Language:** TypeScript

This project follows the Better Agents standard for building production-ready AI agents.

---

## Core Principles

### 1. Scenario Agent Testing

Scenario allows for end-to-end validation of multi-turn conversations and real-world scenarios. Most agent functionality should be tested with Scenario tests, and these MUST be created and maintained strictly using the LangWatch MCP (do not access external Scenario docs).

**CRITICAL**: Every new agent feature MUST be tested with Scenario tests (use LangWatch MCP to access the docs) before considering it complete.

- Write simulation tests for multi-turn conversations
- Validate edge cases
- Ensure business value is delivered
- Test different conversation paths

Best practices:
- NEVER check for regex or word matches in the agent's response, use judge criteria instead
- Use functions on the Scenario scripts for things that can be checked deterministically (tool calls, database entries, etc) instead of relying on the judge
- For the rest, use the judge criteria to check if agent is reaching the desired goal and
- When broken, run on single scenario at a time to debug and iterate faster, not the whole suite
- Write as few scenarios as possible, try to cover more ground with few scenarios, as they are heavy to run
- If user made 1 request, just 1 scenario might be enough, run it at the end of the implementation to check if it works
- ALWAYS consult the Scenario docs **through the LangWatch MCP** on how to install and write scenarios.

### 2. Prompt Management

**ALWAYS** use LangWatch Prompt CLI for managing prompts:

- Use the LangWatch MCP to learn about prompt management, search for Prompt CLI docs
- Never hardcode prompts in your application code
- Store all prompts in the `prompts/` directory as YAML files, use "langwatch prompt create <name>" to create a new prompt
- Run `langwatch prompt sync` after changing a prompt to update the registry

Example prompt structure:
```yaml
# prompts/my_prompt.yaml
model: gpt-4o
temperature: 0.7
messages:
  - role: system
    content: |
      Your system prompt here
  - role: user
    content: |
      {{ user_input }}
```

DO NOT use hardcoded prompts in your application code, example:

BAD:
```
Agent(prompt="You are a helpful assistant.")
```

GOOD:
```python
import langwatch

prompt = langwatch.prompts.get("my_prompt")
Agent(prompt=prompt.prompt)
```

```typescript
import { LangWatch } from "langwatch";

const langwatch = new LangWatch({
  apiKey: process.env.LANGWATCH_API_KEY
});

const prompt = await langwatch.prompts.get("my_prompt")
Agent(prompt=prompt!.prompt)
```

Prompt fetching is very reliable when using the prompts cli because the files are local (double check they were created with the CLI and are listed on the prompts.json file).
DO NOT add try/catch around it and DO NOT duplicate the prompt here as a fallback

Explore the prompt management get started and data model docs if you need more advanced usages such as compiled prompts with variables or messages list.

### 3. Evaluations for specific cases

Only write evaluations for specific cases:

- When a RAG is implemented, so we can evaluate the accuracy given many sample queries (using an LLM to compare expected with generated outputs)
- For classification tasks, e.g. categorization, routing, simple true/false detection, etc
- When the user asks and you are sure an agent scenario wouldn't test the behaviour better

This is because evaluations are good for things when you have a lot of examples, with avery clear
definition of what is correct and what is not (that is, you can just compare expected with generated)
and you are looking for single input/output pairs. This is not the case for multi-turn agent flows.

Create evaluations in Jupyter notebooks under `tests/evaluations/`:

- Generate csv example datasets yourself to be read by pandas with plenty of examples
- Use LangWatch Evaluations API to create evaluation notebooks and track the evaluation results
- Use either a simple == comparison or a direct (e.g. openai) LLM call to compare expected with generated if possible and not requested otherwise

### 4. General good practices

- ALWAYS use the package manager cli commands to init, add and install new dependencies, DO NOT guess package versions, DO NOT add them to the dependencies file by hand.
- When setting up, remember to load dotenv for the tests so env vars are available
- Double check the guidelines on AGENTS.md after the end of the implementation.

---

## Framework-Specific Guidelines

### Mastra Framework

**Always use the Mastra MCP for learning:**

- The Mastra MCP server provides real-time documentation
- Ask it questions about Mastra APIs and best practices
- Follow Mastra's recommended patterns for agent development

**When implementing agent features:**
1. Consult the Mastra MCP: "How do I [do X] in Mastra?"
2. Use Mastra's built-in agent capabilities
3. Follow Mastra's TypeScript patterns and conventions
4. Leverage Mastra's integration ecosystem

**Initial setup:**
1. Use `pnpx mastra init --default` to create a new mastra project, do it before setting up the rest of the project, right after having done `pnpm init`.
2. Then explore the setup it created, the folders, remove what not needed
3. Proceed with the user definition request to implement the agent and test it out
4. Open the UI for user to see using `pnpx mastra dev`

---

## Project Structure

This project follows a standardized structure for production-ready agents:

```
|__ src/           # Main application code
|__ prompts/          # Versioned prompt files (YAML)
|_____ *.yaml
|__ tests/
|_____ evaluations/   # Jupyter notebooks for component evaluation
|________ *.ipynb
|_____ scenarios/     # End-to-end scenario tests
|________ *.test.ts
|__ prompts.json      # Prompt registry
|__ .env              # Environment variables (never commit!)
```

---

## Development Workflow

### When Starting a New Feature:

1. **Understand Requirements**: Clarify what the agent should do
2. **Design the Approach**: Plan which components you'll need
3. **Implement with Prompts**: Use LangWatch Prompt CLI to create/manage prompts
4. **Write Unit Tests**: Test deterministic components
5. **Create Evaluations**: Build evaluation notebooks for probabilistic components
6. **Write Scenario Tests**: Create end-to-end tests using Scenario
7. **Run Tests**: Verify everything works before moving on

### Always:

- ✅ Version control your prompts
- ✅ Write tests for new features
- ✅ Use LangWatch MCP to learn best practices and to work with Scenario tests and evaluations
- ✅ Follow the Agent Testing Pyramid
- ✅ Document your agent's capabilities

### Never:

- ❌ Hardcode prompts in application code
- ❌ Skip testing new features
- ❌ Commit API keys or sensitive data
- ❌ Optimize without measuring (use evaluations first)

---

## Using LangWatch MCP

The LangWatch MCP server provides expert guidance on:

- Prompt management with Prompt CLI
- Writing and maintaining Scenario tests (use LangWatch MCP to learn)
- Creating evaluations
- Best practices for agent development

The MCP will provide up-to-date documentation and examples. For Scenario specifically, always navigate its documentation and examples through the LangWatch MCP instead of accessing it directly.

---

## Getting Started

1. **Set up your environment**: Copy `.env.example` to `.env` and fill in your API keys
2. **Learn the tools**: Ask the LangWatch MCP about prompt management and testing
3. **Start building**: Implement your agent in the `src/` directory
4. **Write tests**: Create scenario tests for your agent's capabilities
5. **Iterate**: Use evaluations to improve your agent's performance

---

## Resources

- **Scenario Documentation**: https://scenario.langwatch.ai/
- **Agent Testing Pyramid**: https://scenario.langwatch.ai/best-practices/the-agent-testing-pyramid
- **LangWatch Dashboard**: https://app.langwatch.ai/
    - **Mastra Documentation**: Use the Mastra MCP for up-to-date docs

---

Remember: Building production-ready agents means combining great AI capabilities with solid software engineering practices. Follow these guidelines to create agents that are reliable, testable, and maintainable.
