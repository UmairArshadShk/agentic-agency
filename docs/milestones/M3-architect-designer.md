# M3: Architect and Designer

**Goal:** after the interview, the architect picks a stack and the designer produces a prototype the client can review and approve in the chat UI.

**Before starting:** decide the one or two golden-path stack templates and the notification channel.

## Scope

- Golden-path templates in `templates/`: each includes the app skeleton, a test runner, a Playwright setup, CI workflow, a preview-deploy hook, and the test-hook convention (stable `data-testid` names).
- `agents/architect.py` (stack check): chooses a template from the draft requirements and records the choice and reasons in the decisions log. It may only pick from the templates.
- `agents/designer.py`: builds a clickable HTML/CSS prototype in the chosen stack's conventions, plus a design tokens file (colors, type, spacing). Tools: file write, Playwright screenshot, preview server.
- Preview pane in the chat UI showing the running prototype, with Approve and Request changes (with a comment) buttons.
- Design gate in the project graph using `interrupt`; change requests loop back to the designer and are logged.
- Notifications (`tools/notify.py`) for gates and escalations over the chosen channel.
- Prompt files and config blocks for architect and designer.

## Tasks

- [ ] Template(s) with CI, preview hook, test-hook convention
- [ ] Architect stack-check agent and decisions log
- [ ] Designer agent, tokens file, screenshots
- [ ] Preview server and UI preview pane
- [ ] Design gate with approve and request-changes loop
- [ ] Notification channel
- [ ] Config and prompts for both agents

## Acceptance criteria

- [ ] For two different draft requirements, the architect picks an appropriate template and explains why; a requirement outside the templates' scope is flagged to the owner instead of forced.
- [ ] The designer's prototype renders in the preview pane and uses the tokens file.
- [ ] Request changes with a comment produces a revised prototype and returns to the gate; Approve moves the workflow on.
- [ ] A notification arrives when the gate is waiting, and the workflow resumes correctly after a restart.
- [ ] Templates build and pass their own CI.

## Out of scope

Final requirements, tickets, architecture document.
