import k2
import torch
import pynini
from src.fst_helpers import fst
import numpy as np

DEVICE = torch.device("cuda", 0)

def fst_to_arc_dict(fst_pynini):
    arcs = []
    aux_labels = []
    states = list(fst_pynini.states())
    final_state = max(states) + 1
    for state_id in states:
        for arc in fst_pynini.arcs(state_id):
            arcs.append([state_id, arc.nextstate, arc.ilabel, float(arc.weight)])
            aux_labels.append(arc.olabel)
            if fst_pynini.final(arc.nextstate) != pynini.Weight.zero('tropical'):
                arcs.append([arc.nextstate, final_state, -1, float(fst_pynini.final(arc.nextstate))])
                aux_labels.append(-1)
    arcs_sorted = sorted(arcs, key=lambda a:a[0])
    aux_labels_sorted = [aux_labels[i] for i in np.argsort([a[0] for a in arcs])]
    arcs_tensor = torch.tensor(arcs_sorted, dtype=torch.int32)
    aux_labels_tensor = torch.tensor(aux_labels_sorted, dtype=torch.int32)
    arc_dict = {
        'arcs': arcs_tensor,
        'aux_labels': aux_labels_tensor
    }
    return arc_dict

def k2_fst(fst_pynini):
    arc_dict = fst_to_arc_dict(fst_pynini)
    k2_fst_obj = k2.Fsa.from_dict(arc_dict).to(DEVICE)
    return k2_fst_obj

f = fst("ŋɛ̂n")
f_k2 = k2_fst(f)
k2.compose(f_k2, f_k2)