"""Prompt module registry - metadata, paths, model compatibility."""

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


PromptTier = Literal["P0", "P1", "P2"]
ModelTier = Literal["strong", "medium", "light"]


@dataclass(frozen=True)
class PromptModule:
    """Single prompt module descriptor."""
    file: str
    name: str
    description: str
    tier: PromptTier
    min_model_tier: ModelTier
    roles: list[str] = field(default_factory=lambda: ["system"])
    intent_tags: list[str] = field(default_factory=list)
    weight: int = 10


class PromptRegistry:
    """Global module registry."""
    _modules: dict[str, PromptModule] = {}

    @classmethod
    def register(cls, module: PromptModule) -> None:
        cls._modules[module.name] = module

    @classmethod
    def get(cls, name: str) -> PromptModule | None:
        return cls._modules.get(name)

    @classmethod
    def list_all(cls) -> list[PromptModule]:
        return list(cls._modules.values())

    @classmethod
    def filter(
        cls,
        *,
        tier: PromptTier | None = None,
        min_model_tier: ModelTier | None = None,
        intent_tags: list[str] | None = None,
    ) -> list[PromptModule]:
        result = list(cls._modules.values())
        if tier:
            result = [m for m in result if m.tier == tier]
        if min_model_tier:
            tier_rank = {"light": 0, "medium": 1, "strong": 2}
            result = [m for m in result if tier_rank.get(m.min_model_tier, 0) <= tier_rank[min_model_tier]]
        if intent_tags:
            result = [m for m in result if any(t in m.intent_tags for t in intent_tags)]
        result.sort(key=lambda m: m.weight, reverse=True)
        return result

    @classmethod
    def clear(cls) -> None:
        cls._modules.clear()


# ==================== Register all modules ====================

# --- Domain P0 ---
PromptRegistry.register(PromptModule(
    file="domain/crystallography.md", name="domain_crystallography",
    description="Crystal structure basics: lattice systems, Miller indices, supercells",
    tier="P0", min_model_tier="light",
    intent_tags=["structure", "crystal", "poscar"], weight=50,
))
PromptRegistry.register(PromptModule(
    file="domain/dft_vasp.md", name="domain_dft_vasp",
    description="DFT/VASP conventions: INCAR parameters, convergence, magnetism",
    tier="P0", min_model_tier="light",
    intent_tags=["vasp", "dft", "calculation"], weight=50,
))
PromptRegistry.register(PromptModule(
    file="domain/elastic_properties.md", name="domain_elastic",
    description="Elastic properties workflow: deformation, EOS fitting, derived moduli",
    tier="P0", min_model_tier="medium",
    intent_tags=["elastic", "mechanical", "eos"], weight=40,
))
PromptRegistry.register(PromptModule(
    file="domain/ml_potentials.md", name="domain_ml_potentials",
    description="ML potentials: supported formats, data preparation, pre-trained models",
    tier="P0", min_model_tier="medium",
    intent_tags=["ml", "machine_learning", "potential", "nn"], weight=40,
))
PromptRegistry.register(PromptModule(
    file="domain/materials_project.md", name="domain_mp",
    description="Materials Project API usage: key requirements, search, limitations",
    tier="P0", min_model_tier="light",
    intent_tags=["mp", "materials_project", "poscar"], weight=45,
))
PromptRegistry.register(PromptModule(
    file="domain/pymatgen_ase.md", name="domain_pymatgen_ase",
    description="pymatgen and ASE data models: structure handling, coordinate systems",
    tier="P0", min_model_tier="light",
    intent_tags=["structure", "poscar", "format", "convert"], weight=45,
))

# --- Domain P1 ---
PromptRegistry.register(PromptModule(
    file="domain/defects.md", name="domain_defects",
    description="Defect physics: vacancy, substitution, interstitial conventions",
    tier="P1", min_model_tier="medium",
    intent_tags=["defect", "vacancy", "substitution", "interstitial"], weight=35,
))
PromptRegistry.register(PromptModule(
    file="domain/surface_interface.md", name="domain_surface_interface",
    description="Surface and interface science: slab models, lattice matching",
    tier="P1", min_model_tier="medium",
    intent_tags=["surface", "slab", "interface"], weight=35,
))

# --- Orchestration P0 ---
PromptRegistry.register(PromptModule(
    file="orchestration/workflow_recipes.md", name="orchestration_recipes",
    description="Standard workflow recipes: tool sequences for common tasks",
    tier="P0", min_model_tier="light",
    intent_tags=["workflow", "recipe", "plan"], weight=60,
))
PromptRegistry.register(PromptModule(
    file="orchestration/tool_chaining.md", name="orchestration_chaining",
    description="Tool chaining rules: prerequisites, state tracking, auto-dependencies",
    tier="P0", min_model_tier="light",
    intent_tags=["tool", "chain", "dependency"], weight=55,
))

# --- Orchestration P1 ---
PromptRegistry.register(PromptModule(
    file="orchestration/tool_selection.md", name="orchestration_selection",
    description="Tool selection decision tree: which tool for which intent",
    tier="P1", min_model_tier="medium",
    intent_tags=["tool", "decision", "guide"], weight=45,
))
PromptRegistry.register(PromptModule(
    file="orchestration/batch_mode.md", name="orchestration_batch",
    description="Multi-parameter batch execution: sweeping, comparison",
    tier="P2", min_model_tier="strong",
    intent_tags=["batch", "sweep", "compare", "multi"], weight=30,
))

# --- Execution P0 ---
PromptRegistry.register(PromptModule(
    file="execution/execution_protocol.md", name="execution_protocol",
    description="Enhanced 3-phase execution protocol with follow-up suggestions",
    tier="P0", min_model_tier="light",
    intent_tags=["protocol", "execute", "plan"], weight=70,
))

# --- Execution P1 ---
PromptRegistry.register(PromptModule(
    file="execution/error_recovery.md", name="execution_error",
    description="Error response patterns: retry, fallback, actionable diagnostics",
    tier="P1", min_model_tier="medium",
    intent_tags=["error", "recover", "retry"], weight=50,
))
PromptRegistry.register(PromptModule(
    file="execution/parameter_validation.md", name="execution_param_validation",
    description="Parameter sanity checks: physical constraints before execution",
    tier="P1", min_model_tier="medium",
    intent_tags=["parameter", "validate", "sanity"], weight=45,
))

# --- Output P1 ---
PromptRegistry.register(PromptModule(
    file="output/result_formatting.md", name="output_formatting",
    description="Result formatting standard: status indicator, key paths, interpretation",
    tier="P1", min_model_tier="medium",
    intent_tags=["output", "result", "format"], weight=50,
))
PromptRegistry.register(PromptModule(
    file="output/next_steps.md", name="output_next_steps",
    description="Follow-up suggestion templates after each type of tool execution",
    tier="P2", min_model_tier="medium",
    intent_tags=["next", "follow", "suggest"], weight=35,
))
PromptRegistry.register(PromptModule(
    file="output/comparison.md", name="output_comparison",
    description="Multi-structure comparison: tables, visualization linking",
    tier="P2", min_model_tier="strong",
    intent_tags=["compare", "table", "summary"], weight=30,
))

# --- Dynamic P1 ---
PromptRegistry.register(PromptModule(
    file="dynamic/session_context.md", name="dynamic_session_context",
    description="Programmatic session state injection",
    tier="P1", min_model_tier="light",
    intent_tags=["session", "context", "state"], weight=65,
))
PromptRegistry.register(PromptModule(
    file="dynamic/model_profiles.md", name="dynamic_model_profiles",
    description="Model capability profiles: which models get which prompt depth",
    tier="P2", min_model_tier="light",
    intent_tags=["model", "capability", "adapt"], weight=60,
))

# --- Few-shot examples P2 ---
PromptRegistry.register(PromptModule(
    file="dynamic/few_shot_examples/convergence_test.md", name="dynamic_fewshot_convergence",
    description="Few-shot example: convergence test workflow",
    tier="P2", min_model_tier="strong",
    intent_tags=["example", "fewshot", "convergence"], weight=25,
))
PromptRegistry.register(PromptModule(
    file="dynamic/few_shot_examples/elastic_constants.md", name="dynamic_fewshot_elastic",
    description="Few-shot example: elastic constants workflow",
    tier="P2", min_model_tier="strong",
    intent_tags=["example", "fewshot", "elastic"], weight=25,
))
PromptRegistry.register(PromptModule(
    file="dynamic/few_shot_examples/ml_prediction.md", name="dynamic_fewshot_ml",
    description="Few-shot example: ML prediction from DFT data workflow",
    tier="P2", min_model_tier="strong",
    intent_tags=["example", "fewshot", "ml", "prediction"], weight=25,
))

# --- Tool docs P0 ---
PromptRegistry.register(PromptModule(
    file="tool_docs.md", name="tool_docs_read_doc",
    description="How to use the read_doc_file tool to look up documentation",
    tier="P0", min_model_tier="light",
    intent_tags=["documentation", "docs", "help", "guide"], weight=55,
))
