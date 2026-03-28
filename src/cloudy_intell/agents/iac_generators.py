"""IaC generation node factories.

These factories follow the same closure pattern as ``domain_nodes.py``:
the outer function captures ``RuntimeContext`` and domain name, the inner
``_node`` function matches the LangGraph signature ``(State) -> State``.

Three node categories:
- **IaC Supervisor**: Reads the architecture input and IaC format, emits a
  planning message, and validates the format is supported for the provider.
- **Domain IaC Generators** (compute, network, storage, database): Each
  generator reads the validated architecture and produces IaC code for its
  domain using the appropriate format (Terraform HCL, CloudFormation YAML,
  or Bicep).
- **IaC Synthesizer**: Merges per-domain IaC outputs into a single cohesive
  IaC document with proper structure (modules, imports, variable blocks, etc.).
"""

import time
from typing import Any, Dict, cast

from langchain_core.messages import SystemMessage

from cloudy_intell.agents.context import RuntimeContext
from cloudy_intell.infrastructure.llm_factory import resolve_execution_llm, resolve_reasoning_llm
from cloudy_intell.infrastructure.logging_utils import get_logger
from cloudy_intell.schemas.models import State

logger = get_logger(__name__)

# ── Format-specific instructions used by domain generators & synthesizer ─────

_FORMAT_INSTRUCTIONS: dict[str, dict[str, str]] = {
    "terraform": {
        "language": "HashiCorp Configuration Language (HCL)",
        "extension": ".tf",
        "structure_guidance": (
            "Generate valid Terraform HCL. Use resource blocks with proper "
            "argument syntax. Include required provider blocks, variable "
            "definitions, and output blocks where appropriate. Use "
            "locals for computed values and data sources for lookups."
        ),
        "merge_guidance": (
            "Combine domain modules into a properly structured Terraform project:\n"
            "- A root main.tf that calls child modules\n"
            "- A variables.tf with all input variables\n"
            "- An outputs.tf with key outputs\n"
            "- One module block per domain (compute, network, storage, database)\n"
            "- A provider block at the top\n"
            "Use consistent naming conventions and proper cross-module references via variables."
        ),
    },
    "cloudformation": {
        "language": "AWS CloudFormation YAML",
        "extension": ".yaml",
        "structure_guidance": (
            "Generate valid CloudFormation YAML template resources. Use proper "
            "resource types (AWS::Service::Resource), Ref and Fn::GetAtt for "
            "cross-references, Parameters for inputs, and Outputs for key values."
        ),
        "merge_guidance": (
            "Combine domain resources into a single CloudFormation YAML template:\n"
            "- AWSTemplateFormatVersion at the top\n"
            "- Description section\n"
            "- Parameters section with all input parameters\n"
            "- Resources section grouping resources by domain with comments\n"
            "- Outputs section with key resource identifiers\n"
            "Ensure all Ref and Fn::GetAtt cross-references between domains are correct."
        ),
    },
    "bicep": {
        "language": "Azure Bicep",
        "extension": ".bicep",
        "structure_guidance": (
            "Generate valid Bicep code. Use proper resource declarations with "
            "API versions, param for inputs, var for locals, and output for "
            "key values. Use modules for logical grouping."
        ),
        "merge_guidance": (
            "Combine domain modules into a properly structured Bicep project:\n"
            "- A main.bicep that references domain modules\n"
            "- Parameter declarations at the top\n"
            "- Module references for each domain\n"
            "- Output declarations for key resources\n"
            "Use consistent naming and proper inter-module references."
        ),
    },
}


def _invoke_with_retries(llm, prompt: str, node_name: str, retries: int = 3) -> str:
    """Invoke an LLM with bounded retries and return the text content."""
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            response = llm.invoke([SystemMessage(content=prompt)])
            content = getattr(response, "content", "")
            if not isinstance(content, str) or not content.strip():
                raise ValueError(f"[{node_name}] Empty response from LLM")
            return content
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt < retries - 1:
                wait_time = 2**attempt
                logger.warning(
                    "%s LLM call failed (attempt %s/%s), retrying in %ss: %s",
                    node_name,
                    attempt + 1,
                    retries,
                    wait_time,
                    exc,
                )
                time.sleep(wait_time)
            else:
                logger.error("%s failed after retries: %s", node_name, exc, exc_info=True)
    return f"[{node_name}] Error: {last_error}"


# ── IaC Supervisor ───────────────────────────────────────────────────────────


def iac_supervisor(ctx: RuntimeContext):
    """Create the IaC supervisor node.

    Reads ``architecture_input`` and ``iac_format`` from state, validates
    that the format is supported for the provider, and emits a planning
    message.  This is intentionally lightweight — the real work is done
    by the parallel domain generators.
    """

    provider = ctx.provider

    def _node(state: State) -> State:
        iac_format = state.get("iac_format") or "terraform"
        architecture_input = state.get("architecture_input") or ""

        if iac_format not in provider.supported_iac_formats:
            supported = ", ".join(provider.supported_iac_formats)
            return cast(
                State,
                {
                    "iac_output": (
                        f"Error: '{iac_format}' is not supported for {provider.display_name}. "
                        f"Supported formats: {supported}"
                    ),
                },
            )

        if not architecture_input.strip():
            return cast(
                State,
                {"iac_output": "Error: No architecture input provided for IaC generation."},
            )

        logger.info(
            "IaC supervisor: generating %s code for %s architecture",
            iac_format,
            provider.display_name,
        )

        return cast(
            State,
            {
                "iac_format": iac_format,
                "architecture_input": architecture_input,
            },
        )

    return _node


# ── Domain IaC Generators ────────────────────────────────────────────────────


def _domain_iac_generator(ctx: RuntimeContext, domain: str):
    """Create one domain IaC generator node using provider metadata.

    Each generator reads the architecture summary and produces IaC code
    for the resources in its domain.  The format-specific instructions
    guide the LLM to produce syntactically correct code.

    Args:
        ctx: Runtime context with LLMs and provider metadata.
        domain: Architecture domain ("compute", "network", "storage", "database").

    Returns:
        A LangGraph node function ``(State) -> State``.
    """

    provider = ctx.provider
    domain_services = provider.domain_services.get(domain, f"{domain} services")
    resource_hints = provider.iac_resource_hints.get(domain, "")

    def _node(state: State) -> State:
        iac_format = state.get("iac_format") or "terraform"
        architecture_input = state.get("architecture_input") or ""

        fmt = _FORMAT_INSTRUCTIONS.get(iac_format, _FORMAT_INSTRUCTIONS["terraform"])

        prompt = f"""You are an Infrastructure as Code expert for {provider.display_name}.
Generate {fmt['language']} code for the **{domain}** domain based on the architecture below.

## Architecture
{architecture_input}

## Your Task
Generate {fmt['language']} code for {domain} resources ({domain_services}).

## Resource Type Hints
Use these resource types where appropriate: {resource_hints}

## Code Requirements
{fmt['structure_guidance']}

- Only generate code for the {domain} domain — do not include resources from other domains.
- Use realistic, production-ready configurations (not placeholder values).
- Include comments explaining key design decisions.
- Follow {provider.display_name} best practices for security and reliability.
- Generate ONLY the code — no explanatory text outside code blocks.

Wrap all code in a single fenced code block with the appropriate language tag.
"""

        try:
            exec_llm = resolve_execution_llm(ctx, state)
            content = _invoke_with_retries(exec_llm, prompt, f"{domain}_iac_generator")
        except Exception as exc:  # noqa: BLE001
            logger.error("[%s_iac_generator] Error: %s", domain, exc, exc_info=True)
            content = f"# Error generating {domain} IaC code: {exc}"

        return cast(
            State,
            {
                "iac_domain_code": {
                    domain: {
                        "code": content,
                        "format": iac_format,
                        "domain": domain,
                    }
                }
            },
        )

    return _node


# Exported factory functions (one per domain)
def compute_iac_generator(ctx: RuntimeContext):
    return _domain_iac_generator(ctx, "compute")


def network_iac_generator(ctx: RuntimeContext):
    return _domain_iac_generator(ctx, "network")


def storage_iac_generator(ctx: RuntimeContext):
    return _domain_iac_generator(ctx, "storage")


def database_iac_generator(ctx: RuntimeContext):
    return _domain_iac_generator(ctx, "database")


# ── IaC Synthesizer ──────────────────────────────────────────────────────────


def iac_synthesizer(ctx: RuntimeContext):
    """Create the IaC synthesizer node that merges domain outputs.

    Collects per-domain IaC code from ``state["iac_domain_code"]`` and
    asks the reasoning LLM to produce a unified, properly structured IaC
    project that combines all domain resources.
    """

    provider = ctx.provider

    def _node(state: State) -> State:
        iac_format = state.get("iac_format") or "terraform"
        iac_domain_code = state.get("iac_domain_code", {})
        architecture_input = state.get("architecture_input") or ""

        if not iac_domain_code:
            return cast(State, {"iac_output": "# No domain IaC code was generated."})

        fmt = _FORMAT_INSTRUCTIONS.get(iac_format, _FORMAT_INSTRUCTIONS["terraform"])

        # Collect all domain code blocks
        domain_sections = []
        for domain in ("compute", "network", "storage", "database"):
            info = iac_domain_code.get(domain, {})
            code = info.get("code", "# No code generated for this domain.")
            domain_sections.append(f"### {domain.upper()} Domain\n{code}")

        all_domain_code = "\n\n---\n\n".join(domain_sections)

        prompt = f"""You are a senior {provider.display_name} Infrastructure as Code architect.
Merge the following per-domain {fmt['language']} code into a single, cohesive, production-ready IaC project.

## Original Architecture
{architecture_input}

## Per-Domain IaC Code
{all_domain_code}

## Merge Instructions
{fmt['merge_guidance']}

## Requirements
- Ensure all cross-domain references are correct (e.g., VPC IDs used by compute resources).
- Remove any duplicate resource definitions.
- Add shared variables/parameters at the top.
- Ensure the final output is syntactically valid {fmt['language']}.
- Include a header comment describing the architecture.
- Generate ONLY the final merged code — no explanatory text outside code blocks.

Wrap the complete output in a single fenced code block with the appropriate language tag.
"""

        merged = _invoke_with_retries(
            resolve_reasoning_llm(ctx, state), prompt, "iac_synthesizer"
        )

        return cast(State, {"iac_output": merged})

    return _node


__all__ = [
    "iac_supervisor",
    "compute_iac_generator",
    "network_iac_generator",
    "storage_iac_generator",
    "database_iac_generator",
    "iac_synthesizer",
]
