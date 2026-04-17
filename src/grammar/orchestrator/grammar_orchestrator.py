"""
Implements the `Paradigm` and `Grammar` classes, which
are the highest-level objects in the registry system.

The `Grammar` class orchestrates all registries for a given language.
"""

from loguru import logger

from src.grammar.classes import Orchestrator
from src.grammar.orchestrator.marker_orchestrator import MarkerOrchestrator
from src.grammar.orchestrator.fst_orchestrator import FstOrchestrator
from src.grammar.orchestrator.feature_orchestrator import FeatureOrchestrator
from src.grammar.registry.lexicon_registry import LexiconRegistry
from src.grammar.registry.paradigm_registry import ParadigmRegistry


class Grammar(Orchestrator):
    """
    Orchestrates all data for a given language.
    """

    def __init__(
        self,
        feature_marker_configs: dict[str, dict],
        contingent_feature_marker_configs: dict[str, dict],
        part_of_speech_configs: dict[str, dict],
        inventory_configs: dict[str, dict],
        pattern_configs: dict[str, dict],
        rule_configs: dict[str, dict],
        feature_definition_configs: dict[str, dict],
        feature_combination_configs: dict[str, dict],
        paradigm_configs: dict[str, dict],
    ):
        self.is_initialized = False

        self.feature_orchestrator = FeatureOrchestrator(
            feature_configs=feature_definition_configs,
            feature_combination_configs=feature_combination_configs,
        )
        self.lexicon_registry = LexiconRegistry(
            config_objects=part_of_speech_configs,
            feature_orchestrator=self.feature_orchestrator,
        )
        self.fst_orchestrator = FstOrchestrator(
            inventory_configs=inventory_configs,
            pattern_configs=pattern_configs,
            rule_configs=rule_configs,
            feature_orchestrator=self.feature_orchestrator,
        )
        self.marker_orchestrator = MarkerOrchestrator(
            contingent_marker_configs=contingent_feature_marker_configs,
            feature_marker_configs=feature_marker_configs,
            feature_orchestrator=self.feature_orchestrator,
        )
        self.paradigm_registry = ParadigmRegistry(
            config_objects=paradigm_configs,
            marker_orchestrator=self.marker_orchestrator,
            lexicon_registry=self.lexicon_registry,
            fst_orchestrator=self.fst_orchestrator,
        )

        self.initialize()

    def initialize(self):
        if all(
            reg is not None
            for reg in [
                self.marker_orchestrator,
                self.lexicon_registry,
                self.fst_orchestrator,
                self.feature_orchestrator,
            ]
        ):
            self.is_initialized = True
            logger.info("All child registries detected, Grammar loaded successfully.")
        else:
            if self.marker_orchestrator is None:
                logger.warning("Grammar received None instead of MarkerOrchestrator")
            if self.fst_orchestrator is None:
                logger.warning("Grammar received None instead of FstOrchestrator")
            if self.lexicon_registry is None:
                logger.warning("Grammar received None instead of LexiconRegistry")
            if self.feature_orchestrator is None:
                logger.warning("Grammar received None instead of FeatureOrchestrator")


if __name__ == "__main__":
    import random
    from src.constants import TIRA_CONFIG_DIR

    reg = Grammar.from_config_dir(TIRA_CONFIG_DIR)

    para = reg.paradigms["verb_no_pronoun"]
    root = random.choice(para.get_filtered_roots())
    stages = para.get_inflection_stages(
        root, {"tam": "imperfective", "class_marker": "l", "deixis": "itive"}
    )
    inflected_paradigm = para.get_subparadigm_table(root)

    para._build_main_graphs()
    random_form = random.choice(inflected_paradigm)["form"].split(";")[0]
    parse = para.get_parses(random_form)

    para._build_edit_graphs()
    random_index = random.randint(0, len(random_form) - 1)
    random_form_list = list(random_form)
    random_form_list.pop(random_index)
    random_form_deletion = "".join(random_form_list)
    search_hits = para.search_form(random_form_deletion)
    search_parses = [para.get_parses(hit_str) for hit_str, _ in search_hits]

    logger.info(f"random_form: {random_form}")
    logger.info(f"parse: {parse}")
    logger.info(f"random_form_deletion: {random_form_deletion}")
    logger.info(f"search_hits: {search_hits}")
    logger.info(f"search_parses: {search_parses}")

    breakpoint()
