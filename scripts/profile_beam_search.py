# TODO: decide how to handle alphabet/symbol table mismatch
# e.g. whether to pad cost matrix before passing to beam search
# or to construct with 0-prob edits for out-of-alphabet symbols

import os

from src.search.beam_search import (
    ascii_table,
    intersect_beam,
    intersect_beam_forward_back,
    decode_beam,
    WfsaCsr,
)
from src.search.edit_modeling import (
    get_random_transition_matrix,
    kl_divergence_from_uniform,
    conditional_kl_divergence_from_uniform,
)
from src.search.edit_graph import (
    intersect_graphs,
    ascii_table,
    alphabet,
    get_search_graph,
    get_query_graph,
    get_edit_factors,
    prepare_cost_matrix_for_edit_graph,
)

import pynini
import graphviz
import numpy as np
from pynini.lib.edit_transducer import EditTransducer
import time
from typing import Any, Literal
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from tqdm import tqdm
from sklearn.linear_model import LinearRegression
import random
from nltk.corpus import words
import nltk
import Levenshtein

nltk.download("words", quiet=True)


"""
FST visualization
"""


def set_symbols(fst: pynini.Fst):
    fst.set_input_symbols(ascii_table)
    fst.set_output_symbols(ascii_table)
    return fst


def print_fst(f):
    f = set_symbols(f)
    tmp_path = "/tmp/null.dot"
    f.draw(tmp_path, portrait=True)
    with open(tmp_path) as file:
        return graphviz.Source(file.read())


"""
Random lexicon/query generation
"""


def generate_random_word(word_len: int | None = None) -> str:
    alpha_start = ord("a")
    alpha_end = ord("z")

    if word_len is None:
        min_word_len = 3
        max_word_len = 10
        word_len = np.random.randint(
            low=min_word_len, high=max_word_len, size=(1,)
        ).item()

    random_ints = np.random.randint(low=alpha_start, high=alpha_end, size=(word_len,))
    random_word = "".join(chr(i) for i in random_ints)
    return random_word


def get_random_lexicon(num_words: int) -> pynini.Fst:
    wordlist = [generate_random_word() for _ in range(num_words)]
    lexicon = pynini.union(*wordlist)
    lexicon.optimize()
    return lexicon


def apply_random_edit(
    word: tuple[int], insert_prob: float, edit_prob_matrix: np.ndarray = None
) -> tuple[int]:
    """
    Apply a random edit (insertion, deletion, substitution) to the input word,
    where the word is a tuple of token indices.

    The type of edit is chosen based on the provided probabilities.
     - insert_prob: probability of insertion (vs. deletion/substitution)
     - edit_prob_matrix: a transition matrix of shape (vocab_size, vocab_size)
        where edit_prob_matrix[i][j] gives the probability of substituting character i
        with character j (when i != j). Assume row/column 0 corresponds to the null token
        for insertions/deletions.

    If edit_prob_matrix is not provided, assume uniform probabilities over edits.

    Choose edit by first deciding whether to insert or delete/substitute based on
    insert_prob, then sample the index to perform the edit at uniformly from the word length,
    and then sample the specific edit from the edit_prob_matrix.
    """
    insert_likelihood = np.random.random()
    is_insert = insert_likelihood < insert_prob

    if edit_prob_matrix is None:
        edit_prob_matrix = np.ones((len(alphabet), len(alphabet))) / len(alphabet)

    if is_insert:
        index = np.random.randint(0, len(word) + 1)
        insert_char = np.random.choice(len(alphabet), p=edit_prob_matrix[0])
        word = word[:index] + (insert_char,) + word[index:]
    else:
        index = np.random.randint(0, len(word))
        original_char = word[index]
        edit_probs = edit_prob_matrix[original_char]
        new_char = np.random.choice(len(alphabet), p=edit_probs)
        if new_char == 0:
            # Deletion
            word = word[:index] + word[index + 1 :]
        else:
            # Substitution
            word = word[:index] + (new_char,) + word[index + 1 :]

    return word


def sample_word_and_edit(
    wordlist: list[str],
    num_edits: int = 5,
    insert_prob: float = 0.3,
    edit_prob_matrix: np.ndarray | None = None,
) -> tuple[str, str]:
    word = random.choice(wordlist)
    edited_word = word
    edited_word_tokenized = tuple([alphabet.index(c) for c in edited_word])

    # use while loop instead of for loop in case of vacuous or colliding edits
    while Levenshtein.distance(word, edited_word) < num_edits:
        edited_word_tokenized = apply_random_edit(
            edited_word_tokenized,
            insert_prob=insert_prob,
            edit_prob_matrix=edit_prob_matrix,
        )
        edited_word = "".join(alphabet[i] for i in edited_word_tokenized)

    return word, edited_word


def get_english_lexicon(num_words: int) -> tuple[list[str], pynini.Fst]:
    wordlist = words.words()
    sampled_words = random.sample(wordlist, num_words)
    sampled_words = [w.lower() for w in sampled_words if w.isalpha()]
    lexicon = pynini.union(*sampled_words)
    lexicon.optimize()
    return sampled_words, lexicon


"""
Profiling
"""


def time_execution(funct: callable) -> tuple[float, Any]:
    start = time.perf_counter()
    result = funct()
    end = time.perf_counter()

    duration = end - start
    return duration, result


def profile_beam_search(
    lexicon: pynini.Fst,
    query: str,
    top_k: int = 5,
    unique_only: bool = True,
    cost_matrix: np.ndarray | None = None,
) -> dict[str, Any]:
    # lexicon preprocessing
    lexicon_preproc_time, lexicon_csr = time_execution(
        lambda: WfsaCsr.from_pynini(lexicon)
    )

    # query preprocessing
    def preproc_query():
        query_fsa = pynini.accep(query)
        query_csr = WfsaCsr.from_pynini(query_fsa)
        return query_csr

    query_preproc_time, query_csr = time_execution(preproc_query)

    # search
    def execute_search():
        results = intersect_beam(
            query_csr,
            lexicon_csr,
            num_beam=top_k,
            fuzzy_search=True,
            unique_only=unique_only,
            cost_matrix=cost_matrix,
        )
        return results

    def execute_search_jit():
        results = intersect_beam(
            query_csr,
            lexicon_csr,
            num_beam=top_k,
            fuzzy_search=True,
            unique_only=unique_only,
            use_jit=True,
            cost_matrix=cost_matrix,
        )
        return results

    search_time, search_results = time_execution(execute_search)
    search_time_jit, _ = time_execution(execute_search_jit)

    total_time = lexicon_preproc_time + query_preproc_time + search_time

    decoded_results = [decode_beam(beam) for beam in search_results]

    return {
        "search_strategy": "beam",
        "lexicon_preproc_time": lexicon_preproc_time,
        "query_preproc_time": query_preproc_time,
        "search_time": search_time,
        "search_time_jit": search_time_jit,
        "total_time": total_time,
        "results": decoded_results,
    }


def profile_beam_search_forward_backward(
    lexicon: pynini.Fst,
    query: str,
    top_k: int = 5,
    unique_only: bool = True,
    cost_matrix: np.ndarray | None = None,
) -> dict[str, Any]:
    # lexicon preprocessing
    def preproc_lexicon():
        lexicon_csr = WfsaCsr.from_pynini(lexicon)
        lexicon_csr_rev = WfsaCsr.from_pynini(pynini.reverse(lexicon).optimize())
        return lexicon_csr, lexicon_csr_rev

    lexicon_preproc_time, (lexicon_csr, lexicon_csr_rev) = time_execution(
        preproc_lexicon
    )

    # query preprocessing
    def preproc_query():
        query_fsa = pynini.accep(query)
        query_csr = WfsaCsr.from_pynini(query_fsa)
        query_csr_rev = WfsaCsr.from_pynini(pynini.reverse(query_fsa).optimize())
        return query_csr, query_csr_rev

    query_preproc_time, (query_csr, query_csr_rev) = time_execution(preproc_query)

    # search
    def execute_search():
        results = intersect_beam_forward_back(
            left_forward=query_csr,
            left_backward=query_csr_rev,
            right_forward=lexicon_csr,
            right_backward=lexicon_csr_rev,
            num_beam=top_k,
            fuzzy_search=True,
            unique_only=unique_only,
            cost_matrix=cost_matrix,
        )
        return results

    def execute_search_jit():
        results = intersect_beam_forward_back(
            left_forward=query_csr,
            left_backward=query_csr_rev,
            right_forward=lexicon_csr,
            right_backward=lexicon_csr_rev,
            num_beam=top_k,
            fuzzy_search=True,
            unique_only=unique_only,
            use_jit=True,
            cost_matrix=cost_matrix,
        )
        return results

    search_time, search_results = time_execution(execute_search)
    search_time_jit, _ = time_execution(execute_search_jit)

    total_time = lexicon_preproc_time + query_preproc_time + search_time

    decoded_results = [decode_beam(beam) for beam in search_results]

    return {
        "search_strategy": "beam_forward_backward",
        "lexicon_preproc_time": lexicon_preproc_time,
        "query_preproc_time": query_preproc_time,
        "search_time": search_time,
        "search_time_jit": search_time_jit,
        "total_time": total_time,
        "results": decoded_results,
    }


def profile_graph_search(
    lexicon: pynini.Fst,
    sigma: pynini.Fst,
    query: str,
    top_k: int = 5,
    cost_matrix: np.ndarray | None = None,
) -> dict[str, Any]:
    # lexicon preprocessing
    def preproc_lexicon():
        edit_dict = (
            prepare_cost_matrix_for_edit_graph(cost_matrix, alphabet)
            if cost_matrix is not None
            else {}
        )
        left_factor, right_factor = get_edit_factors(sigma=sigma, **edit_dict)
        search_graph = get_search_graph(lexicon, right_factor)
        return left_factor, search_graph

    lexicon_preproc_time, (left_factor, search_graph) = time_execution(preproc_lexicon)

    # query preprocessing
    def preproc_query():
        query_graph = get_query_graph(query, left_factor)
        return query_graph

    query_preproc_time, query_graph = time_execution(preproc_query)

    # search
    def execute_search():
        result_dict = intersect_graphs(query_graph, search_graph, top_k=top_k)
        return result_dict

    search_time, search_results = time_execution(execute_search)
    result_tuples = search_results["result"]
    lattice_num_states = search_results["lattice_num_states"]

    total_time = lexicon_preproc_time + query_preproc_time + search_time

    return {
        "search_strategy": "edit_graph",
        "lexicon_preproc_time": lexicon_preproc_time,
        "query_preproc_time": query_preproc_time,
        "search_time": search_time,
        "total_time": total_time,
        "results": result_tuples,
        "lattice_num_states": lattice_num_states,
    }


"""
Data visualization and inspection
"""


def prepare_df_for_plotting(time_df: pd.DataFrame) -> pd.DataFrame:
    # melt df so that we have a single "time_seconds" and "search_stage" column for plotting
    time_df = time_df.melt(
        id_vars=[
            "search_strategy",
            "num_words",
            "num_states",
            "query_len",
            "num_beam",
            "recall",
            "results",
            "query",
            "target",
            "lattice_num_states",
            "alpha",
        ],
        value_vars=[
            "lexicon_preproc_time",
            "query_preproc_time",
            "search_time",
            "search_time_jit",
        ],
        var_name="search_stage",
        value_name="time_seconds",
    )

    # track JIT separately from non-JIT beam search
    jit_mask = (time_df["search_stage"] == "search_time_jit") & (
        time_df["search_strategy"].str.startswith("beam")
    )
    time_df.loc[jit_mask, "search_strategy"] = (
        time_df.loc[jit_mask, "search_strategy"] + "_jit"
    )

    # merge "search_time_jit" with "search_time"
    time_df.loc[jit_mask, "search_stage"] = "search_time"

    # get inverse of time for better visualization (higher is better)
    time_df["words_per_sec"] = time_df["time_seconds"].apply(
        lambda x: 1 / x if x > 0 else float("inf")
    )
    return time_df


def time_by_lexicon_size(
    plot_df: pd.DataFrame,
    feature: Literal["num_states", "num_words"] = "num_states",
    num_beam: int = 50,
):
    """
    seaborn lineplot showing search time by lexicon size, with separate colors for beam search and graph search
    and separate facets for lexicon preprocessing and search time (exclude query preprocessing)
    with line style for query length
    fix num_beam for beam search
    """
    sns.set_style("whitegrid")
    plot_mask = (
        (plot_df["search_stage"] == "search_time")
        & (plot_df["alpha"].eq(0.0))
        & (
            (plot_df["search_strategy"] == "edit_graph")
            | (plot_df["num_beam"] == num_beam)
        )
    )
    sns.lineplot(
        data=plot_df[plot_mask],
        x=feature,
        y="words_per_sec",
        hue="search_strategy",
    )
    plt.show()


def time_by_num_beam(plot_df: pd.DataFrame):
    """
    seaborn lineplot with x-axis as lexicon size and y-axis as search time
    faceted by query length with line color by num_beam, only showing beam search results
    at search stage
    """
    sns.set_style("whitegrid")
    beam_plot_df = plot_df[
        (plot_df["search_strategy"].isin(["beam", "beam_jit"]))
        & plot_df["search_stage"].eq("search_time")
        & plot_df["alpha"].eq(0.0)
    ]
    g = sns.FacetGrid(
        beam_plot_df,
        height=4,
        aspect=1.5,
        col="query_len",
        sharey=True,
    )
    g.map_dataframe(
        sns.lineplot,
        "num_states",
        "words_per_sec",
        hue="num_beam",
        style="search_strategy",
    )
    g.set_axis_labels("Lexicon Size (Number of States)", "Words Per Second")
    g.set_titles("Query Length = {col_name}")
    g.add_legend(title="Beam Size")
    plt.show()


def plot_recall(plot_df: pd.DataFrame):
    """
    plot recall by alpha, faceted by query length and colored by num_beam,
    only showing non-jit results
    """
    sns.set_style("whitegrid")
    recall_plot_df = plot_df[
        (plot_df["search_strategy"].str.startswith("beam"))
        & (~plot_df["search_strategy"].str.endswith("jit"))
        & plot_df["search_stage"].eq("search_time")
    ]
    sns.lineplot(
        data=recall_plot_df,
        x="alpha",
        y="recall",
        hue="num_beam",
        style="search_strategy",
        markers=True,
        dashes=False,
    )
    plt.show()


def get_linreg_coeffs(plot_df, num_beam: int = 50) -> pd.DataFrame:
    """
    fit linear regression models to predict search time based on
    number of states and number of words in the lexicon
    """
    coeffs = []
    for strategy in plot_df["search_strategy"].unique():
        if strategy.startswith("beam"):
            strategy_mask = (plot_df["search_strategy"] == strategy) & (
                plot_df["num_beam"] == num_beam
            )
        else:
            strategy_mask = plot_df["search_strategy"] == strategy
        strategy_df = plot_df[strategy_mask]
        strategy_df = strategy_df[strategy_df["search_stage"] == "search_time"]
        strategy_df = strategy_df.dropna(
            subset=["num_states", "num_words", "words_per_sec"]
        )

        X_words = strategy_df[["num_words"]]
        X_states = strategy_df[["num_states"]]
        y = strategy_df["words_per_sec"]

        word_model = LinearRegression()
        word_model.fit(X_words, y)

        state_model = LinearRegression()
        state_model.fit(X_states, y)

        coeffs.append((strategy, word_model.coef_[0], word_model.intercept_, "words"))
        coeffs.append(
            (strategy, state_model.coef_[0], state_model.intercept_, "states")
        )

    return pd.DataFrame(
        coeffs, columns=["search_strategy", "slope", "intercept", "feature"]
    )


def get_words_per_sec(plot_df: pd.DataFrame, num_beam: int = 50) -> pd.DataFrame:
    """
    calculate words per second for each search strategy
    averaged across all lexicon sizes and query lengths
    """
    wps_rows = []
    for strategy in plot_df["search_strategy"].unique():
        if strategy.startswith("beam"):
            strategy_mask = (plot_df["search_strategy"] == strategy) & (
                plot_df["num_beam"] == num_beam
            )
        else:
            strategy_mask = plot_df["search_strategy"] == strategy
        strategy_df = plot_df[strategy_mask]
        strategy_df = strategy_df[strategy_df["search_stage"] == "search_time"]
        words_per_sec = strategy_df["words_per_sec"].mean()
        wps_rows.append((strategy, words_per_sec))

    return pd.DataFrame(wps_rows, columns=["search_strategy", "words_per_sec"])


"""
Main profiling function
"""


def perform_beam_search_fb(
    size: int,
    lexicon: pynini.Fst,
    num_states: int,
    target: str,
    query: str,
    query_len: int,
    num_beam: int,
    graph_results_set: set,
    cost_matrix: np.ndarray | None = None,
    alpha: float = 0.0,
):
    beam_fb_result = profile_beam_search_forward_backward(
        lexicon, query, top_k=num_beam, unique_only=True, cost_matrix=cost_matrix
    )

    # get forward-backward beam search recall
    fb_results_set = set(word for word, _ in beam_fb_result["results"])
    fb_recall = (
        len(graph_results_set.intersection(fb_results_set)) / len(graph_results_set)
        if graph_results_set
        else 1.0
    )

    beam_search_fb_row = {
        **beam_fb_result,
        "num_words": size,
        "num_states": num_states,
        "query_len": query_len,
        "recall": fb_recall,
        "num_beam": num_beam,
        "query": query,
        "target": target,
        "alpha": alpha,
    }

    return beam_search_fb_row


def perform_beam_search(
    size: int,
    lexicon: pynini.Fst,
    num_states: int,
    target: str,
    query: str,
    query_len: int,
    graph_results_set: set[str],
    num_beam: int,
    cost_matrix: np.ndarray | None = None,
    alpha: float = 0.0,
):
    beam_result = profile_beam_search(
        lexicon, query, top_k=num_beam, unique_only=True, cost_matrix=cost_matrix
    )

    # beam search may miss some results due to pruning
    # calculate recall based on graph search results
    beam_results_set = set(word for word, _ in beam_result["results"])
    recall = (
        len(graph_results_set.intersection(beam_results_set)) / len(graph_results_set)
        if graph_results_set
        else 1.0
    )

    beam_result_row = {
        **beam_result,
        "num_words": size,
        "num_states": num_states,
        "query_len": query_len,
        "recall": recall,
        "num_beam": num_beam,
        "query": query,
        "target": target,
        "alpha": alpha,
    }

    return beam_result_row


def perform_graph_search(
    size: int,
    sigma: pynini.Fst,
    lexicon: pynini.Fst,
    num_states: int,
    target: str,
    query: str,
    query_len: int,
    alpha: float | None = None,
    cost_matrix: np.ndarray | None = None,
):
    graph_result = profile_graph_search(
        lexicon=lexicon, sigma=sigma, query=query, top_k=10, cost_matrix=cost_matrix
    )
    graph_result_row = {
        **graph_result,
        "num_words": size,
        "num_states": num_states,
        "query_len": query_len,
        "query": query,
        "target": target,
        "alpha": alpha,
    }

    return graph_result, graph_result_row


def run_profiler() -> pd.DataFrame:
    # run beam search with JIT so that function is pre-compiled
    graph = WfsaCsr.from_pynini(pynini.accep("foo"))
    intersect_beam(graph, graph, fuzzy_search=True, use_jit=True)

    time_rows = []

    # alphabet FSA: same regardless of lexicon
    sigma = pynini.union(*[c for c in alphabet if c]).optimize()

    # Hyperparameters for profiling
    # - alphas: alpha values to pass to edit cost matrix construction
    # - insert_prob: probability of insertion vs. deletion/substitution
    #       when generating random edits
    # - lexicon sizes: num words in search lexicon
    # - num queries: number of random queries to sample per lexicon
    # - beam sizes: number of beams to keep for beam search

    # alpha values in log space from [1e-3, 100]
    alphas = np.logspace(-3, 2, 5)
    insert_prob = 0.3
    # reverse for pyschological benefit
    # (loop speeds up as it progresses instead of slowing down)
    # lexicon_sizes = np.arange(1_000, 101_000, 10_000)[::-1]
    lexicon_sizes = [20]
    num_queries = 3
    beam_sizes = [10, 20, 50, 100, 200]

    for size in tqdm(lexicon_sizes):
        for alpha in tqdm(alphas):
            edit_probs = get_random_transition_matrix(alphabet, alpha)
            edit_costs = 1 - edit_probs

            wordlist, lexicon = get_english_lexicon(size)
            num_states = lexicon.num_states()
            for _ in range(num_queries):
                target, query = sample_word_and_edit(
                    wordlist,
                    num_edits=5,
                    edit_prob_matrix=edit_probs,
                    insert_prob=insert_prob,
                )
                query_len = len(query)

                graph_result, graph_result_row = perform_graph_search(
                    size=size,
                    sigma=sigma,
                    lexicon=lexicon,
                    num_states=num_states,
                    target=target,
                    query=query,
                    query_len=query_len,
                )

                graph_result_w_cost, graph_result_row_w_cost = perform_graph_search(
                    size=size,
                    sigma=sigma,
                    lexicon=lexicon,
                    num_states=num_states,
                    target=target,
                    query=query,
                    query_len=query_len,
                    alpha=alpha,
                    cost_matrix=edit_costs,
                )

                time_rows.extend([graph_result_row, graph_result_row_w_cost])
                graph_results_set = set(word for word, _ in graph_result["results"])
                graph_results_w_cost_set = set(graph_result_w_cost["results"])

                for num_beam in beam_sizes:
                    beam_result_row = perform_beam_search(
                        size=size,
                        lexicon=lexicon,
                        num_states=num_states,
                        target=target,
                        query=query,
                        query_len=query_len,
                        graph_results_set=graph_results_set,
                        num_beam=num_beam,
                    )

                    beam_result_row_w_costs = perform_beam_search(
                        size=size,
                        lexicon=lexicon,
                        num_states=num_states,
                        target=target,
                        query=query,
                        query_len=query_len,
                        graph_results_set=graph_results_w_cost_set,
                        num_beam=num_beam,
                        cost_matrix=edit_costs,
                        alpha=alpha,
                    )

                    beam_search_fb_row = perform_beam_search_fb(
                        size=size,
                        lexicon=lexicon,
                        num_states=num_states,
                        target=target,
                        query=query,
                        query_len=query_len,
                        num_beam=num_beam,
                        graph_results_set=graph_results_set,
                    )

                    beam_search_fb_row_w_costs = perform_beam_search_fb(
                        size=size,
                        lexicon=lexicon,
                        num_states=num_states,
                        target=target,
                        query=query,
                        query_len=query_len,
                        num_beam=num_beam,
                        graph_results_set=graph_results_w_cost_set,
                        cost_matrix=edit_costs,
                        alpha=alpha,
                    )

                    time_rows.extend(
                        [
                            beam_result_row,
                            beam_result_row_w_costs,
                            beam_search_fb_row,
                            beam_search_fb_row_w_costs,
                        ]
                    )

    time_df = pd.DataFrame(time_rows)
    plot_df = prepare_df_for_plotting(time_df)
    return plot_df


if __name__ == "__main__":
    profile_csv = "./tmp/beam_search_profile.csv"
    if os.path.exists(profile_csv):
        df = pd.read_csv(profile_csv)
    else:
        df = None

    if df is None:
        df = run_profiler()
        df.to_csv(profile_csv, index=False)
    coeffs = get_linreg_coeffs(df)
    words_per_sec = get_words_per_sec(df)

    breakpoint()
