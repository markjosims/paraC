def get_different_items(d1, d2):
    """Return the set of keys and values that differ between two dicts."""
    keys1 = set(d1.keys())
    keys2 = set(d2.keys())
    diff_keys = keys1.symmetric_difference(keys2)

    diff_values = {k: (d1[k], d2[k]) for k in keys1.intersection(keys2) if d1[k] != d2[k]}

    return diff_keys, diff_values


def filter_query_and_hits(query_dict, hit_list):
    query_filtered = {
        k: v for k,v in query_dict.items()
        if any(k in parse for parse in hit_list)
    }
    hits_filtered = []
    for hit in hit_list:
        hit_filtered = {
            k: v for k,v in hit.items()
            if k in query_filtered
        }
        hits_filtered.append(hit_filtered)
    return query_filtered,hits_filtered