"""Names of tools an agent may be granted in config. Implementations land with their milestones.

Jira status-changing tools are deliberately absent: only workflow code moves tickets.
"""

KNOWN_TOOLS: frozenset[str] = frozenset(
    {
        "ask_user",
        "read_requirements",
        "write_requirements",
        "jira_read",
        "jira_create_ticket",
        "jira_comment",
        "read_file",
        "write_file",
        "edit_file",
        "screenshot",
        "preview_server",
        "scaffold_repo",
        "shell",
        "git",
        "github",
        "test_runner",
        "pr_diff",
        "github_comment",
        "dependency_check",
        "playwright",
        "preview_env",
        "staging_env",
        "screenshot_diff",
    }
)
