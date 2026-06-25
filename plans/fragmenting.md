# Fragmenting

## Why

At present any form input change causes page-wide re-render and form`->`state syncing.
This causes both excessive latency and instability, if an invalid form input causes a crash when syncing form to state.
A better pattern is to isolate each input node so that inputting data does not cause any other widgets to re-render, user input is validated upon submission and form`->`state syncing only occurs when saving to disk or previewing YAML tree.

## Definition of done

- [ ] Form inputs are wrapped with a fragment for every editor page
- [ ] All form fields have input validation
- [ ] Form`->`state syncing only occurs on writing to disk or YAML tree preview

## Context

- `st.fragment` decorator wraps a function with a fragment so that no change to content rendered within the function will trigger a page-wide re-render unless `st.rerun()` is called
- Validation functions kept in `validation.py`

## Progress per page

- [x] ../src/pages/editors/editor_base/editor_base.py
  - [x] disk write and YAML preview trigger `read_form_to_state`
- [x] ../src/pages/editors/inventory.py
  - [x] `st.fragment` added
  - [x] form input validation added
  - [x] `read_form_to_state` only on disk write or YAML preview
  - [x] smoke test page
- [ ] ../src/pages/editors/contingent_markers.py:
  - [ ] `st.fragment` added
  - [ ] form input validation added
  - [ ] `read_form_to_state` only on disk write or YAML preview
  - [ ] smoke test page
- [ ] ../src/pages/editors/feature_combinations.py:
  - [ ] `st.fragment` added
  - [ ] form input validation added
  - [ ] `read_form_to_state` only on disk write or YAML preview
  - [ ] smoke test page
- [ ] ../src/pages/editors/patterns.py:
  - [ ] `st.fragment` added
  - [ ] form input validation added
  - [ ] `read_form_to_state` only on disk write or YAML preview
  - [ ] smoke test page
- [ ] ../src/pages/editors/feature_markers.py
  - [ ] `st.fragment` added
  - [ ] form input validation added
  - [ ] `read_form_to_state` only on disk write or YAML preview
  - [ ] smoke test page
- [ ] ../src/pages/editors/feature_values.py
  - [ ] `st.fragment` added
  - [ ] form input validation added
  - [ ] `read_form_to_state` only on disk write or YAML preview
  - [ ] smoke test page
- [ ] ../src/pages/editors/lexicon.py
  - [ ] `st.fragment` added
  - [ ] form input validation added
  - [ ] `read_form_to_state` only on disk write or YAML preview
  - [ ] smoke test page
- [ ] ../src/pages/editors/morpheme_sequence.py
  - [ ] `st.fragment` added
  - [ ] form input validation added
  - [ ] `read_form_to_state` only on disk write or YAML preview
  - [ ] smoke test page
- [ ] ../src/pages/editors/morpheme_set.py
  - [ ] `st.fragment` added
  - [ ] form input validation added
  - [ ] `read_form_to_state` only on disk write or YAML preview
  - [ ] smoke test page
- [x] ../src/pages/editors/paradigm.py
  - [x] `st.fragment` added
  - [ ] form input validation added
  - [x] `read_form_to_state` only on disk write or YAML preview
  - [x] smoke test page
- [x] ../src/pages/editors/patterns.py
  - [x] `st.fragment` added
  - [x] form input validation added
  - [x] `read_form_to_state` only on disk write or YAML preview
  - [x] rerun when user requests test run
  - [x] smoke test page
- [x] ../src/pages/editors/rules.py
  - [x] `st.fragment` added
  - [x] form input validation added
  - [x] `read_form_to_state` only on disk write or YAML preview
  - [x] rerun when user requests test run
  - [x] smoke test page
