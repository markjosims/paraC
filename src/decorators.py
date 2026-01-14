# cache stacks
from pynini.lib import paradigms
import os
import pynini
import hashlib
import pickle
from functools import wraps
from time import time, perf_counter
from typing import Any, List, Optional, Tuple
import contextlib
from loguru import logger
from src.constants.paths import CACHE_DIR

# cache stacks
FST_CACHE = []
OUTPUT_CACHE = []
CACHE_LIMIT = int(os.environ.get("TIRA_PARSER_CACHE_LIMIT", 100))

@contextlib.contextmanager
def Timer(operation_name: str):
    """
    A context manager to time a block of code and log the duration.
    
    Usage:
        with Timer("FST Composition"):
            result = k2.compose(fsa_a, fsa_b)
    """
    start_time = perf_counter()
    
    # Print the start message immediately
    logger.info(f"START: {operation_name}...")
    
    # 'yield' passes control back to the 'with' block's body
    try:
        yield
        
    finally:
        # This code runs after the 'with' block finishes, even if an error occurred.
        end_time = perf_counter()
        duration = end_time - start_time
        
        # Log the result, formatted to 4 decimal places
        logger.info(f"END:   {operation_name} finished in {duration:.4f} seconds.")

def get_output_cache_path(args, kwargs, func_name: str) -> Tuple[str, str]:
    """
    Arguments:
        args:   Positional arguments to be hashed.
        kwargs: Keyword arguments to be hashed.
    Returns:
        args_str:  String representation of hashable arguments.
        cache_path: Path to the cache file.
    Raises:
        TypeError: If any argument is not hashable.
    """
    args_str = get_args_str(args, kwargs)
    cache_key = hashlib.md5((func_name + args_str).encode()).hexdigest()
    cache_path = os.path.join(
        CACHE_DIR,
        f"{cache_key}.output"
    )
    return args_str, cache_path

def get_fst_cache_path(args, kwargs, func_name: str, num_fst: int) -> Tuple[str, List[str]]:
    """
    Arguments:
        args:   Positional arguments to be hashed.
        kwargs: Keyword arguments to be hashed.
    Returns:
        args_str:  String representation of hashable arguments.
        cache_paths: List of paths to the cache files.
    Raises:
        TypeError: If any argument is not hashable.
    """
    args_str = get_args_str(args, kwargs)
    cache_key = hashlib.md5((func_name + args_str).encode()).hexdigest()
    cache_paths = []
    for i in range(num_fst):
        cache_path = os.path.join(
            CACHE_DIR,
            f"{cache_key}_{i}.fst"
        )
        cache_paths.append(cache_path)
    return args_str, cache_paths

def get_args_str(args, kwargs):
    args_for_key = list(args)
    kwargs_for_key = kwargs.copy()
    for i, arg in enumerate(args):
        if type(arg) is list:
            arg = tuple(sorted(arg))
        elif type(arg) is paradigms.Paradigm:
            # Paradigm objects are not hashable, so use their name
            arg = arg.name
        args_for_key[i] = arg
        try:
            hash(arg)
        except TypeError:
            raise TypeError(f"Type {type(arg)} of arg {arg} is not hashable")
    for key, value in kwargs.items():
        if type(value) is list:
            value = tuple(sorted(value))
            kwargs_for_key[key] = value
        if type(value) is paradigms.Paradigm:
                # Paradigm objects are not hashable, so use their name
            kwargs_for_key[key] = value.name
        elif key.startswith('main_') and isinstance(value, pynini.Fst):
            # only one main lemmatizer/analyzer/inflector is expected
            # this can be ignored for caching purposes
            kwargs_for_key.pop(key)
            value = None
        try:
            hash(value)
        except TypeError:
            raise TypeError(f"Type {type(value)} of kwarg {key}={value} is not hashable")
    args_str = str(args_for_key)+str(kwargs_for_key)
    return args_str

def cache_is_updated(current_file: str, cache_path: str) -> bool:
    """
    Check if the cache is updated relative to the script file.
    """
    if os.path.isdir(current_file):
        file_date = max(
            os.path.getmtime(os.path.join(current_file, f))
            for f in os.listdir(current_file)
        )
    else:
        file_date = os.path.getmtime(current_file)
    if os.path.exists(cache_path):
        cache_date = os.path.getmtime(cache_path)
        return cache_date >= file_date
    return False

def put_cached_output_on_stack(cache_path: str, output: Any) -> None:
    """
    Store cached output on the in-memory cache stack.
    """
    global OUTPUT_CACHE
    OUTPUT_CACHE.append((cache_path, output))
    if len(OUTPUT_CACHE) > CACHE_LIMIT:
        OUTPUT_CACHE.pop(0)

def put_cached_fst_on_stack(cache_path: str, fst: pynini.Fst) -> None:
    """
    Store cached FST on the in-memory cache stack.
    """
    global FST_CACHE
    FST_CACHE.append((cache_path, fst))
    if len(FST_CACHE) > CACHE_LIMIT:
        FST_CACHE.pop(0)

def get_cached_output_from_stack(cache_path: str) -> Any:
    """
    Retrieve cached output from the in-memory cache stack if available.
    """
    global OUTPUT_CACHE
    for i, (path, output) in enumerate(OUTPUT_CACHE):
        if path == cache_path:
            # Move the accessed cache to the top of the stack
            OUTPUT_CACHE.append(OUTPUT_CACHE.pop(i))
            return output
    return None

def get_cached_fst_from_stack(cache_path: str) -> pynini.Fst:
    """
    Retrieve cached FST from the in-memory cache stack if available.
    """
    global FST_CACHE
    for i, (path, fst) in enumerate(FST_CACHE):
        if path == cache_path:
            # Move the accessed cache to the top of the stack
            FST_CACHE.append(FST_CACHE.pop(i))
            return fst
    return None


def output_cache(current_file: str, build_only: bool = False) -> Any:
    """
    Arguments:
        current_file:  The file path of the current module.
    Returns:
        out:             Python object loaded from cache or generated by the decorated function.

    Decorator that caches the output of a function returning any Python object.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time()
            os.makedirs(CACHE_DIR, exist_ok=True)
            try:
                args_str, cache_path = get_output_cache_path(args, kwargs, func.__name__)
            except TypeError as e:
                # if args are not hashable, skip caching
                logger.debug(
                    f"Building output for function {func.__name__} "
                    f"with args {args} and kwargs {kwargs} without caching (unhashable args): {e}"
                )
                out = func(*args, **kwargs)
                end_time = time()
                logger.debug(f"Function {func.__name__} took {end_time - start_time} seconds")
                return out

            cached_out = None
            if not build_only:
                cached_out = get_cached_output_from_stack(cache_path)
            if cached_out is not None:
                logger.debug(
                    f"Loaded output for function {func.__name__} "
                    f"with args {args_str} from in-memory cache"
                )
                end_time = time()
                logger.debug(f"Loading from in-memory cache took {end_time - start_time} seconds")
                return cached_out
            elif cache_is_updated(current_file, cache_path) and build_only:
                logger.debug(
                    f"Output exists for function {func.__name__} "
                    f"with args {args_str} and cache {cache_path}, "
                    "skipping loading due to build_only=True"
                )
                return None
            elif cache_is_updated(current_file, cache_path):
                with open(cache_path, 'rb') as f:
                    logger.debug(
                        f"Loaded output for function {func.__name__} "
                        f"with args {args_str} from cache {cache_path}"
                    )
                    out = pickle.load(f)
                    end_time = time()
                    logger.debug(f"Loading cache took {end_time - start_time} seconds")
            else:
                logger.debug(
                    f"Building output for function {func.__name__} "
                    f"with args {args_str} and cache {cache_path}"
                )
                out = func(*args, **kwargs)
                if type(out) is paradigms.Paradigm:
                    _log_paradigm_stats(out, func.__name__, args_str)
                end_time = time()
                logger.debug(f"Function {func.__name__} took {end_time - start_time} seconds")
                with open(cache_path, 'wb') as f:
                    pickle.dump(out, f)
            put_cached_output_on_stack(cache_path, out)
            return out
        return wrapper
    return decorator


def _log_fst_stats(
        fst_list: List[pynini.Fst],
        func_name: str,
        args_str: str,
        fst_names: Optional[List[str]]=None
    ) -> None:
    """Log the number of states and arcs for each FST in the list."""
    if fst_names is None:
        fst_names = [f"FST {i}" for i in range(len(fst_list))]
    for name, fst_obj in zip(fst_names, fst_list):
        num_states = fst_obj.num_states()
        num_arcs = sum(fst_obj.num_arcs(state) for state in fst_obj.states())
        logger.debug(
            f"{name} from {func_name}({args_str}): "
            f"{num_states} states, {num_arcs} arcs"
        )

def _log_paradigm_stats(paradigm: paradigms.Paradigm, func_name: str, args_str: str) -> None:
    """Log FST stats for analyzer, lemmatizer, and inflector of the paradigm."""
    fst_names = ["Analyzer", "Lemmatizer", "Inflector"]
    fst_list = [
        paradigm.analyzer,
        paradigm.lemmatizer,
        paradigm.inflector
    ]
    _log_fst_stats(fst_list, func_name, args_str, fst_names)

def fst_cache(current_file: str, num_fst: int=1) -> pynini.Fst:
    """
    Arguments:
        current_file:  The file path of the current module.
        num_fst:        Number of FSTs returned by the decorated function.
    Returns:
        f:              FST loaded from cache or generated by the decorated function.

    Decorator that caches the output of an FST-generating function.

    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            os.makedirs(CACHE_DIR, exist_ok=True)
            try:
                args_str, cache_paths = get_fst_cache_path(args, kwargs, func.__name__, num_fst=num_fst)
            except TypeError as e:
                # if args are not hashable, skip caching
                logger.debug(
                    f"Building FST for function {func.__name__} "
                    f"with args {args} and kwargs {kwargs} without caching (unhashable args): {e}"
                )
                f = func(*args, **kwargs)
                return f
            cached_fsts = []
            for cache_path in cache_paths:
                cached_f = get_cached_fst_from_stack(cache_path)
                cached_fsts.append(cached_f)
            if not any(f is None for f in cached_fsts):
                # all FSTS found in in-memory cache
                logger.debug(
                    f"Loaded FST for function {func.__name__} "
                    f"with args {args_str} from in-memory cache (num_fst={num_fst})"
                )
                if num_fst == 1:
                    return cached_fsts[0]
                return cached_fsts
            elif all(cache_is_updated(current_file, cache_path) for cache_path in cache_paths):
                logger.debug(
                    f"Loaded FST for function {func.__name__} "
                    f"with args {args_str} from cache {cache_paths[0]} (num_fst={num_fst})"
                )
                f = [pynini.Fst.read(cache_path) for cache_path in cache_paths]
            else:
                logger.debug(
                    f"Building FST for function {func.__name__} "
                    f"with args {args_str} and cache {cache_paths[0]} (num_fst={num_fst})"
                )
                f = func(*args, **kwargs)
                if num_fst == 1:
                    f = [f]
                _log_fst_stats(f, func.__name__, args_str)
                for fst_obj, cache_path in zip(f, cache_paths):
                    fst_obj.write(cache_path)
                    put_cached_fst_on_stack(cache_path, fst_obj)
            if num_fst == 1:
                return f[0]
            return f
        return wrapper
    return decorator