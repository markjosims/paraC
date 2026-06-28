"""
Implements the MorphemeSequence class, which handles concatenative morphology
by sequencing Lexicons, Paradigms, Patterns, and Rules, and the MorphemeSequenceRegistry
class, which manages multiple MorphemeSequence configurations.
"""

from loguru import logger
import os
import pynini
from pynini.lib import pynutil
from src.config_utils.config_walker import validate_file_reference_str
from src.fst_utils import FsaLike, Acceptor
from src.grammar.orchestrator.fst_orchestrator import FstOrchestrator
from src.grammar.orchestrator.feature_orchestrator import serialize_feature_str, stringify_features
from src.grammar.classes import Registry
from src.grammar.registry.lexicon_registry import LexiconRegistry, Lexicon
from src.grammar.registry.paradigm_registry import EDIT_COST, EDIT_COST, EDIT_BOUND, ParadigmRegistry, Paradigm
from src.grammar.registry.morpheme_set_registry import MorphemeSetRegistry, MorphemeSet
from src.grammar.registry.rule_registry import Rule
from src.grammar.registry.feature_values_registry import Feature
from typing import Any
from tqdm import tqdm
from itertools import product


class MorphemeSequence:
    """
    Defines a sequence of morphemes and provides logic for generating
    inflected forms and analysis strings.
    """

    def __init__(
        self,
        name: str,
        sequence_data: list[dict],
        lexicon_registry: LexiconRegistry,
        paradigm_registry: ParadigmRegistry,
        morpheme_set_registry: MorphemeSetRegistry,
        fst_orchestrator: FstOrchestrator,
        source_path: str | None = None,
        fixed_features: dict[str, str] | None = None,
    ):
        self.name = name
        self.sequence_data = sequence_data
        self.lexicon_registry = lexicon_registry
        self.paradigm_registry = paradigm_registry
        self.morpheme_set_registry = morpheme_set_registry
        self.fst_orchestrator = fst_orchestrator
        self.source_path = source_path
        self.fixed_features = fixed_features or {}
        self.is_initialized = False

        # To be populated during initialization
        self.morphemes: list[Paradigm | Lexicon | MorphemeSet | Rule | Acceptor] = []
        self.features: set[Feature] = set()
        self.main_graphs_built = False
        self.edit_graphs_built = False

    @classmethod
    def from_config(
        cls,
        config: dict,
        lexicon_registry: LexiconRegistry,
        paradigm_registry: ParadigmRegistry,
        morpheme_set_registry: MorphemeSetRegistry,
        fst_orchestrator: FstOrchestrator,
    ) -> "MorphemeSequence":
        source_path = config.get("source_path")
        name = config.get("name")
        if not name and source_path:
            name = os.path.splitext(os.path.basename(source_path))[0]

        return cls(
            name=name or "[UNNAMED]",
            sequence_data=config.get("data", []),
            lexicon_registry=lexicon_registry,
            paradigm_registry=paradigm_registry,
            morpheme_set_registry=morpheme_set_registry,
            fst_orchestrator=fst_orchestrator,
            source_path=source_path,
            fixed_features=config.get("fixed_features"),
        )

    def to_dict(self) -> dict:
        data = []
        for item in self.sequence_data:
            new_item = item.copy()
            if new_item["kind"] in ["Lexicon", "Paradigm", "Rule", "MorphemeSet"]:
                new_item["value"] = validate_file_reference_str(new_item["value"])
            data.append(new_item)

        return {
            "kind": "MorphemeSequence",
            "name": self.name,
            "data": data,
            "source_path": self.source_path,
            "fixed_features": self.fixed_features,
        }

    def initialize(self):
        """
        Populate `self.morphemes` and `self.features` by iterating through `self.sequence_data`,
        resolving the reference for each morpheme or operation based on its type and, when
        applicable, adding all features exponed by that morpheme.
        """
        for item in self.sequence_data:
            morpheme_kind = item["kind"]
            morpheme_value = item["value"]

            resolved = None
            if morpheme_kind == "Lexicon":
                resolved = self.lexicon_registry.get_lexicon(morpheme_value)
                if resolved:
                    self.features.update([f for f in resolved.features])
                    self.features.update([f for f in resolved.lexical_features])
            elif morpheme_kind == "Paradigm":
                resolved = self.paradigm_registry.get_paradigm(morpheme_value)
                if resolved:
                    self.features.update([f for f in resolved.features])
                    # Paradigms also have access to lexical features of their lexicon
                    if resolved.lexicon:
                        self.features.update(
                            [f for f in resolved.lexicon.lexical_features]
                        )
            elif morpheme_kind == "Pattern":
                resolved = self.fst_orchestrator.fsa(morpheme_value)
            elif morpheme_kind == "Rule":
                resolved = self.fst_orchestrator.get_rule(morpheme_value)
            elif morpheme_kind == "MorphemeSet":
                resolved = self.morpheme_set_registry.get_morpheme_set(morpheme_value)
                if resolved:
                    self.features.update([f for f in resolved.features])

            if resolved is None:
                logger.error(
                    f"Could not resolve {morpheme_kind} reference: {morpheme_value}"
                )

            self.morphemes.append(resolved)

        self.is_initialized = True
        logger.info(
            f"MorphemeSequence '{self.name}' initialized with {len(self.morphemes)} steps."
        )

    def get_valid_feature_combinations(self) -> list[dict[str, str]]:
        """
        Get all valid combinations of features for the morpheme sequence.
        """

        # For now just make cartesian product of all non-fixed features
        # TODO: implement proper feature combination logic
        feature_value_sets = [
            feature.values
            for feature in self.features
            if feature not in self.fixed_features
        ]
        return [
            dict(
                zip(
                    [f.name for f in self.features if f not in self.fixed_features],
                    values,
                )
            )
            for values in product(*feature_value_sets)
        ]

    def get_sequence_fst(
        self, features: dict[str, str], stems: list[str | pynini.Fst] | None = None
    ) -> pynini.Fst:
        """`
        Builds the sequence graph for a specific feature set by concatenating/composing
        sequence items. If `stems` is provided, it must contain one stem for each
        Lexicon or Paradigm step in the sequence.
        """
        if not self.is_initialized:
            self.initialize()

        # Merge fixed features and check for conflicts
        features = features.copy()
        for feature_name, feature_value in self.fixed_features.items():
            # if an unmarked feature is requested, don't throw error on conflict
            if (
                (feature_name in features)
                and (features[feature_name] != "unmarked")
                and (features[feature_name] != feature_value)
            ):
                raise ValueError(
                    f"Conflict for fixed feature {feature_name}: sequence expects {feature_value}, got {features[feature_name]}"
                )
            features[feature_name] = feature_value

        # Initialize with empty string acceptor
        result_fst = pynini.accep("")
        stem_idx = 0

        for item, resolved in zip(self.sequence_data, self.morphemes):
            morpheme_kind = item["kind"]

            if resolved is None:
                continue

            step_fst = None
            try:
                if morpheme_kind == "Lexicon":
                    assert isinstance(resolved, Lexicon)
                    if stems:
                        if stem_idx >= len(stems):
                            raise ValueError(
                                f"Not enough stems provided for Lexicon step {resolved.name}"
                            )
                        stem = stems[stem_idx]
                        stem_idx += 1
                        step_fst = self.fst_orchestrator._cast_fsalike_to_fsa(
                            stem, is_word=True
                        )
                    else:
                        step_fst = resolved.analyses_to_roots(features)
                elif morpheme_kind == "Paradigm":
                    assert isinstance(resolved, Paradigm)
                    if stems:
                        if stem_idx >= len(stems):
                            raise ValueError(
                                f"Not enough stems provided for Paradigm step {resolved.name}"
                            )
                        stem = stems[stem_idx]
                        stem_idx += 1
                        step_fst = resolved.inflect(stem, features)
                    else:
                        step_fst = resolved.get_subparadigm_inflect_graph(features)
                elif morpheme_kind == "MorphemeSet":
                    assert isinstance(resolved, MorphemeSet)
                    step_fst = resolved.analysis_to_morpheme(**features)
                elif morpheme_kind == "Pattern":
                    # resolved is pynini.Fst from fst_orchestrator.fsa()
                    step_fst = resolved
                elif morpheme_kind == "Rule":
                    # resolved is a Rule instance
                    assert isinstance(resolved, Rule)
                    result_fst = self.fst_orchestrator.apply_rule(result_fst, resolved)
                    continue

                if step_fst is not None:
                    # skip if fst is empty (no paths)
                    if step_fst.start() == pynini.NO_STATE_ID:
                        logger.warning(
                            f"Step {morpheme_kind} {resolved} returned empty FST, skipping."
                        )
                        continue
                    result_fst.concat(step_fst)

            except KeyError as e:
                logger.warning(
                    f"Skipping step {morpheme_kind} {resolved} due to KeyError: {e}"
                )
                continue

        return result_fst.optimize()

    def inflect(
        self, stems: list[str | pynini.Fst], features: dict[str, str]
    ) -> pynini.Fst:
        """
        Inflect a sequence of stems according to the provided feature set.
        `stems` should be a list containing one stem (str or Fst) for each
        Lexicon or Paradigm step in the sequence.
        """
        return self.get_sequence_fst(features, stems=stems)

    def get_inflection_stages(
        self, stems: list[str | pynini.Fst], features: dict[str, str]
    ) -> list[dict[str, Any]]:
        """
        Get intermediate stages of inflection for a MorphemeSequence.
        """
        if not self.is_initialized:
            self.initialize()

        # Merge fixed features and check for conflicts
        features = features.copy()
        for f, v in self.fixed_features.items():
            if f in features and features[f] != v and features[f] != "unmarked":
                raise ValueError(
                    f"Conflict for fixed feature {f}: sequence expects {v}, got {features[f]}"
                )
            features[f] = v

        current_fst = pynini.accep("")
        stem_idx = 0
        stages = []

        # Initial stage
        stages.append(
            {
                "step": 0,
                "kind": "START",
                "value": "",
                "form": "",
                "fst": current_fst,
            }
        )

        for i, (item, resolved) in enumerate(zip(self.sequence_data, self.morphemes)):
            morpheme_kind = item["kind"]
            morpheme_value = item["value"]
            step_info = {"step": i + 1, "kind": morpheme_kind, "value": morpheme_value}

            step_fst = None
            try:
                if morpheme_kind == "Lexicon":
                    assert isinstance(resolved, Lexicon)
                    stem = stems[stem_idx]
                    stem_idx += 1
                    step_fst = self.fst_orchestrator._cast_fsalike_to_fsa(
                        stem, is_word=False
                    )
                elif morpheme_kind == "Paradigm":
                    assert isinstance(resolved, Paradigm)
                    stem = stems[stem_idx]
                    stem_idx += 1
                    step_fst = resolved.inflect(stem, features)
                elif morpheme_kind == "MorphemeSet":
                    assert isinstance(resolved, MorphemeSet)
                    step_fst = resolved.analysis_to_morpheme(**features)
                elif morpheme_kind == "Pattern":
                    step_fst = resolved
                elif morpheme_kind == "Rule":
                    assert isinstance(resolved, Rule)
                    # apply the rule to the current FST
                    # as rules don't concatenate a new FST
                    current_fst = self.fst_orchestrator.apply_rule(
                        current_fst, resolved
                    )

                if step_fst is not None:
                    if step_fst.start() == pynini.NO_STATE_ID:
                        logger.warning(
                            f"Step {morpheme_kind} {resolved} returned empty FST, skipping."
                        )
                    else:
                        current_fst = current_fst + step_fst

            except KeyError as e:
                logger.warning(
                    f"Skipping step {morpheme_kind} {resolved} due to KeyError: {e}"
                )

            # Extract form string for the stage
            form = ""
            try:
                forms = self.fst_orchestrator.fsm_strings(current_fst)
                if forms:
                    form = forms[0]
            except Exception:
                form = "<ERROR>"

            stages.append({**step_info, "form": form, "fst": current_fst})

        stages.append(
            {
                "step": len(self.morphemes) + 1,
                "kind": "FINAL",
                "value": "",
                "form": self.fst_orchestrator.fsm_strings(
                    current_fst, strip_all_tags=True
                )[0],
            }
        )

        return stages

    def get_inflected_form(
        self, features: dict[str, str], stems: list[str] | None = None
    ) -> list[str]:
        """
        Generates inflected forms based on feature vector.
        """
        fst = self.get_sequence_fst(features, stems=stems)
        return self.fst_orchestrator.fsm_strings(fst)

    # TODO: for now `_build_main_graphs`, `get_parses`,
    # `_build_edit_graphs` and `search_form` are mostly copy-pasted
    # from the paradigm registry.
    # During OOP -> FP conversion, these methods should be refactored
    # to apply to both config types.

    def build_all_graphs(self):
        self._build_main_graphs()
        self._build_edit_graphs()

    def _build_main_graphs(self):
        """
        Build a main graph for the paradigm by computing the union of all
        possible paths through the paradigm based on the feature markers and
        contingent markers, allowing for efficient inflection and parsing of
        forms.

        The graph is built by iterating through all stems and combinations
        and accumulating a list of root[features...] -> form transducers, then
        computing a union over each transducer as the main Inflector graph, and
        the Parser graph by inverting the Inflector graph.
        """
        logger.info(
            f"Building main (inflector and parser) graphs for morpheme sequence {self.name}..."
        )

        # for now generate list of roots naively by getting cartesian
        # product of all possible roots for any lexical morpheme
        # (Lexicon or Paradigm)
        stems: list[list[str]] = []
        for morpheme in self.morphemes:
            if isinstance(morpheme, Lexicon):
                morpheme_stems = morpheme.get_roots(
                    fixed_lexical_features=self.fixed_features
                )
                stems.append(morpheme_stems)
            elif isinstance(morpheme, Paradigm):
                morpheme_stems = morpheme.get_filtered_roots()
                if any(
                    feature not in morpheme.fixed_lexical_features
                    for feature in self.fixed_features
                ):
                    # morpheme sequence has stricter set of fixed lexical features
                    # than paradigm, so further filtering is needed
                    roots_with_features = morpheme.lexicon.get_roots(
                        self.fixed_features
                    )
                    morpheme_stems = list(
                        set(morpheme_stems) & set(roots_with_features)
                    )
                stems.append(morpheme_stems)

        stem_combos = list(product(*stems))

        inflect_fst_list = []
        # nested loops through cartesian product of stems and features
        # O(thicc)
        for stem_sequence in tqdm(stem_combos):
            for feature_combo in tqdm(
                self.get_valid_feature_combinations(),
                desc=f"Inflecting roots for morpheme sequence {self.name}",
            ):
                inflected_result = self.inflect(stem_sequence, feature_combo)
                feature_str = stringify_features(feature_combo)

                stem_sequence_str = "-".join(stem_sequence)
                inflect_input = self.fst_orchestrator.fsa(
                    stem_sequence_str + feature_str
                )
                inflect_output = pynini.project(inflected_result, "output")
                inflect_fst = pynini.cross(inflect_input, inflect_output)

                inflect_fst.optimize()
                inflect_fst_list.append(inflect_fst)

        inflect_graph = pynini.union(*inflect_fst_list)
        inflect_graph.optimize()

        parse_graph = pynini.invert(inflect_graph)
        parse_graph.optimize()

        self.inflect_graph = inflect_graph
        self.parse_graph = parse_graph
        self.main_graphs_built = True

        logger.info("Main graphs built.")

    def _build_edit_graphs(self):
        """
        Build left and right edit factors and a pre-compiled
        searchable lexicon.

        Based on code in the [Pynini EditTransducer](https://github.com/kylebgorman/pynini/blob/27ce19048193358cd362a4de6b157cb43ab6e2eb/pynini/lib/edit_transducer.py)
        """
        logger.info(f"Building edit graph for morpheme sequence {self.name}...")
        if not self.main_graphs_built:
            raise ValueError("Cannot build edit graph without main graph")

        # shorthands for ease of life
        insert = self.fst_orchestrator.insert
        delete = self.fst_orchestrator.delete
        substitute = self.fst_orchestrator.substitute
        sigma = self.fst_orchestrator.sigma
        sigma_star = self.fst_orchestrator.sigma_star

        wfsa = self.fst_orchestrator.wfsa

        # build single edit transducers
        insert_fst = pynutil.insert(wfsa(insert, weight=EDIT_COST / 2))
        delete_fst = pynini.cross(sigma, wfsa(delete, weight=EDIT_COST / 2))
        substitute_fst = pynini.cross(sigma, wfsa(substitute, weight=EDIT_COST / 2))
        edit_fst = pynini.union(insert_fst, delete_fst, substitute_fst).optimize()

        # build left search factor
        left_factor = sigma_star.copy()
        for _ in range(EDIT_BOUND):
            left_factor.concat(edit_fst.ques).concat(sigma_star)
        left_factor.optimize()

        # build right factor from left
        right_factor = pynini.invert(left_factor)
        insert_label = self.fst_orchestrator.symbols.find(insert)
        delete_label = self.fst_orchestrator.symbols.find(delete)
        label_pairs = [(insert_label, delete_label), (delete_label, insert_label)]
        right_factor = right_factor.relabel_pairs(ipairs=label_pairs)

        # compose right factor with lexicon
        form_lattice = pynini.project(self.inflect_graph, "output")
        searchable_lexicon = right_factor @ form_lattice

        # set attrs
        self.left_factor = left_factor
        self.right_factor = right_factor
        self.searchable_lexicon = searchable_lexicon

        self.edit_graphs_built = True

        logger.info(f"Edit graphs built for morpheme sequence {self.name}.")

    def get_parses(
        self, form: FsaLike, serialize: bool = False
    ) -> list[str | dict[str, str]]:
        """
        Computes a parse lattice by composing the input string with the main parse graph
        then returns a list of strings of all candidate parses, where feature values
        are specified in the format "ROOT[feat=val][feat=val][feat=val]..."

        If `serialize=True`, casts the feature string to a dict using `serialize_feature_str`
        """
        if not self.main_graphs_built:
            logger.info("`get_parses` called without main graphs built, building...")
            self.build_all_graphs()

        form_fsa = self.fst_orchestrator._cast_fsalike_to_fsa(form, is_word=True)
        parse_lattice = form_fsa @ self.parse_graph
        parse_strings = self.fst_orchestrator.fsm_strings(parse_lattice)

        if serialize:
            serialized_parses = []
            for parse in parse_strings:
                feature_index = parse.index("[")
                root = parse[:feature_index]
                feature_str = parse[feature_index:]
                feature_dict = serialize_feature_str(feature_str)
                feature_dict["root"] = root
                serialized_parses.append(feature_dict)
            return serialized_parses

        return parse_strings
    
    def search_form(
        self, query: FsaLike, nshortest: int = 5
    ) -> list[tuple[str, float]]:
        """
        Searches the lexicon for fuzzy matches of an input string and returns
        the nshortest hits along with their edit costs.
        """
        if not self.edit_graphs_built:
            logger.info("`search_form` called without edit graphs built, building...")
            self.build_all_graphs()

        query_fsa = self.fst_orchestrator._cast_fsalike_to_fsa(query)
        search_lattice = (query_fsa @ self.left_factor) @ self.searchable_lexicon
        form_hits = self.fst_orchestrator.fsm_strings_and_weights(
            search_lattice, nshortest=nshortest
        )
        return form_hits


class MorphemeSequenceRegistry(Registry):
    """
    Registry for MorphemeSequence objects.
    """

    def __init__(
        self,
        lexicon_registry: LexiconRegistry,
        paradigm_registry: ParadigmRegistry,
        fst_orchestrator: FstOrchestrator,
        morpheme_set_registry: MorphemeSetRegistry,
        data: dict[str, MorphemeSequence] | None = None,
        config_objects: dict[str, dict] | None = None,
    ):
        self.lexicon_registry = lexicon_registry
        self.paradigm_registry = paradigm_registry
        self.morpheme_set_registry = morpheme_set_registry
        self.fst_orchestrator = fst_orchestrator
        super().__init__(
            kind="MorphemeSequence", data=data, config_objects=config_objects
        )

    def load_all_configs(self) -> dict[str, MorphemeSequence]:
        config_items: dict[str, MorphemeSequence] = {}
        for config in self.config_objects.values():
            config_data = self.load_data_from_config(config)
            for key in config_data:
                if key in config_items:
                    error = f"Duplicate MorphemeSequence '{key}' found in multiple config files."
                    logger.error(error)
                    raise ValueError(error)
            config_items.update(config_data)
        return config_items

    def load_data_from_config(self, config: dict) -> dict[str, MorphemeSequence]:
        sequence = MorphemeSequence.from_config(
            config=config,
            lexicon_registry=self.lexicon_registry,
            paradigm_registry=self.paradigm_registry,
            fst_orchestrator=self.fst_orchestrator,
            morpheme_set_registry=self.morpheme_set_registry,
        )
        return {sequence.name: sequence}

    def get_sequence(self, name: str) -> MorphemeSequence | None:
        return self.data.get(name)

    def initialize_sequences(self):
        for sequence in self.data.values():
            sequence.initialize()
