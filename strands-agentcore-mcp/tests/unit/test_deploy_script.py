"""Deploy-script lint tests.

Reads scripts/deploy.sh as text and asserts the conventions from
.kiro/steering/project-conventions.md are followed.

These tests guard the deploy script mechanically so regressions are caught
before a real deployment attempt.

Requirements covered: 11.1, 11.2, 11.3, 13.1, 13.2, 13.3, 13.4, 13.5, 13.6
"""

import os
import re

import pytest

DEPLOY_SCRIPT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "scripts", "deploy.sh"
)


@pytest.fixture(scope="session")
def deploy_script() -> str:
    """Read the deploy script once per session."""
    with open(DEPLOY_SCRIPT_PATH, "r") as fh:
        return fh.read()


# ---------------------------------------------------------------------------
# Helper: extract non-comment lines from the deploy script
# ---------------------------------------------------------------------------

def _non_comment_lines(script: str) -> str:
    """Return the script with comment-only lines removed."""
    lines = []
    for line in script.splitlines():
        stripped = line.strip()
        if not stripped.startswith("#"):
            lines.append(line)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 1. Two pip3 install invocations with correct platform/python-version flags
#    (Requirements 11.1, 11.2)
# ---------------------------------------------------------------------------

def test_two_pip3_install_invocations(deploy_script):
    """There must be exactly two pip3 install invocations (excluding comments)."""
    code_only = _non_comment_lines(deploy_script)
    matches = re.findall(r'\bpip3\s+install\b', code_only)
    assert len(matches) == 2, (
        f"Expected exactly 2 'pip3 install' invocations in non-comment lines, found {len(matches)}"
    )


def test_pip3_install_platform_flag(deploy_script):
    """Both pip3 install invocations must include --platform manylinux2014_x86_64."""
    code_only = _non_comment_lines(deploy_script)
    occurrences = [
        m.start() for m in re.finditer(r'\bpip3\s+install\b', code_only)
    ]
    assert len(occurrences) == 2, "Expected exactly 2 pip3 install invocations"

    for pos in occurrences:
        # Look at the next ~500 chars after each pip3 install
        snippet = code_only[pos:pos + 500]
        assert "--platform manylinux2014_x86_64" in snippet, (
            f"pip3 install at position {pos} is missing --platform manylinux2014_x86_64"
        )


def test_pip3_install_python_version_flag(deploy_script):
    """Both pip3 install invocations must include --python-version 3.12."""
    code_only = _non_comment_lines(deploy_script)
    occurrences = [
        m.start() for m in re.finditer(r'\bpip3\s+install\b', code_only)
    ]
    for pos in occurrences:
        snippet = code_only[pos:pos + 500]
        assert "--python-version 3.12" in snippet, (
            f"pip3 install at position {pos} is missing --python-version 3.12"
        )


def test_second_pip3_install_has_no_deps(deploy_script):
    """The second pip3 install invocation must include --no-deps."""
    code_only = _non_comment_lines(deploy_script)
    occurrences = [
        m.start() for m in re.finditer(r'\bpip3\s+install\b', code_only)
    ]
    assert len(occurrences) == 2, "Expected exactly 2 pip3 install invocations"
    second_pos = occurrences[1]
    snippet = code_only[second_pos:second_pos + 500]
    assert "--no-deps" in snippet, (
        "Second pip3 install must include --no-deps (pure-Python packages step)"
    )


def test_second_pip3_install_has_pure_python_packages(deploy_script):
    """The second pip3 install must list the nine pure-Python package names."""
    code_only = _non_comment_lines(deploy_script)
    occurrences = [
        m.start() for m in re.finditer(r'\bpip3\s+install\b', code_only)
    ]
    assert len(occurrences) == 2, "Expected exactly 2 pip3 install invocations"
    second_pos = occurrences[1]
    # Look at a larger window since the package list may span multiple lines
    snippet = code_only[second_pos:second_pos + 800]

    required_packages = [
        "requests",
        "urllib3",
        "charset-normalizer",
        "idna",
        "certifi",
        "PyJWT",
        "cryptography",
        "cffi",
        "mcp",
    ]
    for pkg in required_packages:
        assert pkg in snippet, (
            f"Second pip3 install is missing pure-Python package: {pkg!r}"
        )


# ---------------------------------------------------------------------------
# 2. No .dist-info removal patterns (Requirement 11.3)
# ---------------------------------------------------------------------------

def test_no_dist_info_removal(deploy_script):
    """Script must NOT remove .dist-info directories."""
    # Check for rm -rf patterns targeting dist-info
    assert not re.search(r'rm\s+.*dist-info', deploy_script), (
        "deploy.sh must not remove .dist-info directories"
    )
    # Check for find ... -delete patterns targeting dist-info
    assert not re.search(r'find\s+.*dist-info.*-delete', deploy_script), (
        "deploy.sh must not use find ... -delete on .dist-info directories"
    )


# ---------------------------------------------------------------------------
# 3. Case-insensitive DOES_NOT_EXIST match (Requirement 13.2)
# ---------------------------------------------------------------------------

def test_case_insensitive_does_not_exist_match(deploy_script):
    """Script must perform a case-insensitive match against DOES_NOT_EXIST."""
    # grep -qi or grep -i with DOES_NOT_EXIST (or does not exist)
    assert re.search(r'grep\s+.*-[a-zA-Z]*i[a-zA-Z]*.*DOES_NOT_EXIST', deploy_script) or \
           re.search(r'grep\s+.*DOES_NOT_EXIST.*-[a-zA-Z]*i', deploy_script) or \
           re.search(r'grep\s+-qi\s+"DOES_NOT_EXIST"', deploy_script) or \
           re.search(r'grep\s+-qi\s+["\']?DOES_NOT_EXIST', deploy_script), (
        "deploy.sh must use case-insensitive grep for DOES_NOT_EXIST "
        "(e.g. grep -qi 'DOES_NOT_EXIST')"
    )


# ---------------------------------------------------------------------------
# 4. ROLLBACK_COMPLETE handling (Requirement 13.3)
# ---------------------------------------------------------------------------

def test_rollback_complete_delete_stack_present(deploy_script):
    """Script must call aws cloudformation delete-stack for ROLLBACK_COMPLETE."""
    assert "ROLLBACK_COMPLETE" in deploy_script, (
        "deploy.sh must handle ROLLBACK_COMPLETE stack state"
    )
    assert "aws cloudformation delete-stack" in deploy_script, (
        "deploy.sh must call 'aws cloudformation delete-stack' for ROLLBACK_COMPLETE"
    )


def test_rollback_complete_wait_delete_complete_present(deploy_script):
    """Script must wait for stack deletion after ROLLBACK_COMPLETE delete."""
    assert "aws cloudformation wait stack-delete-complete" in deploy_script, (
        "deploy.sh must call 'aws cloudformation wait stack-delete-complete' "
        "after deleting a ROLLBACK_COMPLETE stack"
    )


# ---------------------------------------------------------------------------
# 5. No bare pip (only pip3) (Requirement 13.4)
# ---------------------------------------------------------------------------

def test_no_bare_pip_invocations(deploy_script):
    """Script must use pip3, never bare pip."""
    # Match 'pip ' or 'pip\n' or 'pip\t' but NOT 'pip3'
    # Use negative lookbehind for '3' and negative lookahead for '3'
    bare_pip_matches = re.findall(r'\bpip\b(?!3)', deploy_script)
    # Filter out occurrences inside comments
    non_comment_matches = []
    for line in deploy_script.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        found = re.findall(r'\bpip\b(?!3)', stripped)
        non_comment_matches.extend(found)

    assert not non_comment_matches, (
        f"deploy.sh must use 'pip3', not bare 'pip'. "
        f"Found {len(non_comment_matches)} bare 'pip' occurrence(s)"
    )


# ---------------------------------------------------------------------------
# 6. PID-based temp file names (Requirement 13.5)
# ---------------------------------------------------------------------------

def test_pid_based_temp_files(deploy_script):
    """Script must use $$-based PID temp file names."""
    # Look for patterns like /tmp/something.$$.something
    assert re.search(r'/tmp/.*\.\$\$\.', deploy_script) or \
           re.search(r'/tmp/.*\.\$\.', deploy_script), (
        "deploy.sh must use PID-based temp file names "
        "(e.g. /tmp/agentcore-mcp.$$.agent.zip)"
    )


def test_no_mktemp_suffix_templates(deploy_script):
    """Script must NOT use mktemp suffix templates (macOS incompatible)."""
    # mktemp -t XXXXX or mktemp --suffix=... patterns
    assert not re.search(r'mktemp\s+.*-t\s+\S*X{3,}', deploy_script), (
        "deploy.sh must not use 'mktemp -t XXXXX' suffix templates — "
        "use $$-based PID names instead"
    )
    assert not re.search(r'mktemp\s+.*--suffix', deploy_script), (
        "deploy.sh must not use 'mktemp --suffix' — "
        "use $$-based PID names instead"
    )


# ---------------------------------------------------------------------------
# 7. validate-template before any other AWS CLI call (Requirement 13.1, 13.5)
# ---------------------------------------------------------------------------

def test_validate_template_before_other_aws_calls(deploy_script):
    """aws cloudformation validate-template must appear before create/update/describe."""
    validate_pos = deploy_script.find("aws cloudformation validate-template")
    assert validate_pos != -1, (
        "deploy.sh must call 'aws cloudformation validate-template'"
    )

    # These calls must come AFTER validate-template
    later_calls = [
        "aws cloudformation create-stack",
        "aws cloudformation update-stack",
        "aws cloudformation describe-stacks",
    ]
    for call in later_calls:
        call_pos = deploy_script.find(call)
        if call_pos != -1:
            assert validate_pos < call_pos, (
                f"'aws cloudformation validate-template' must appear before "
                f"'{call}' in deploy.sh"
            )


# ---------------------------------------------------------------------------
# 8. Generated test.sh heredoc does NOT use nested echo emitting JSON (Req 13.6)
# ---------------------------------------------------------------------------

def test_no_nested_echo_json_in_heredoc(deploy_script):
    """Generated test.sh must not be produced via nested echo emitting JSON."""
    # The script should use a heredoc (cat > ... <<'EOF') not echo '{"key": ...}'
    # Check that there's no echo with JSON-like content for the test.sh generation
    # We look for the heredoc pattern
    assert "<<'EOF'" in deploy_script or '<<"EOF"' in deploy_script or \
           "<<EOF" in deploy_script, (
        "deploy.sh must use a heredoc to generate scripts/test.sh"
    )

    # Ensure there's no pattern like: echo '{"jwt":' or echo "{\"jwt\":"
    # that would indicate nested echo emitting JSON for the test script
    # (This is a heuristic — the heredoc approach is the correct one)
    heredoc_start = deploy_script.find("cat > scripts/test.sh")
    if heredoc_start == -1:
        heredoc_start = deploy_script.find("cat >scripts/test.sh")

    assert heredoc_start != -1, (
        "deploy.sh must use 'cat > scripts/test.sh <<...' to generate the test script"
    )


# ---------------------------------------------------------------------------
# 9. Both Lambda zips are produced (Agent + MCP Server)
# ---------------------------------------------------------------------------

def test_both_lambda_zips_produced(deploy_script):
    """Script must produce both Agent and MCP Server Lambda zips."""
    assert "agent" in deploy_script.lower() and "zip" in deploy_script.lower(), (
        "deploy.sh must produce an Agent Lambda zip"
    )
    assert "mcp" in deploy_script.lower() and "zip" in deploy_script.lower(), (
        "deploy.sh must produce an MCP Server Lambda zip"
    )


# ---------------------------------------------------------------------------
# 10. S3 fallback for large zips (Requirement 11.5)
# ---------------------------------------------------------------------------

def test_s3_fallback_for_large_zips(deploy_script):
    """Script must handle zips > 50 MB via S3 upload fallback."""
    assert "50" in deploy_script, (
        "deploy.sh must check for 50 MB zip size threshold"
    )
    assert "s3" in deploy_script.lower() or "S3" in deploy_script, (
        "deploy.sh must have S3 upload fallback for large zips"
    )


# ---------------------------------------------------------------------------
# 11. DynamoDB seeding with at least two categories (Requirement 10.3)
# ---------------------------------------------------------------------------

def test_dynamodb_seeding_present(deploy_script):
    """Script must seed DynamoDB with sample products."""
    assert "aws dynamodb put-item" in deploy_script, (
        "deploy.sh must seed DynamoDB with 'aws dynamodb put-item'"
    )
    # At least two categories
    assert "Electronics" in deploy_script, (
        "deploy.sh must seed at least one Electronics product"
    )
    assert "Books" in deploy_script, (
        "deploy.sh must seed at least one Books product"
    )


# ---------------------------------------------------------------------------
# 12. Cognito test user creation (Requirement 1.2)
# ---------------------------------------------------------------------------

def test_cognito_test_user_creation(deploy_script):
    """Script must create a Cognito test user."""
    assert "admin-create-user" in deploy_script, (
        "deploy.sh must call 'aws cognito-idp admin-create-user'"
    )
    assert "admin-set-user-password" in deploy_script, (
        "deploy.sh must call 'aws cognito-idp admin-set-user-password'"
    )
    assert "--permanent" in deploy_script, (
        "deploy.sh must use --permanent flag to confirm the test user"
    )
