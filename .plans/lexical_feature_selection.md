# lexical feature selection

Desideratum: User can reference lexical features specified within a paradigm in morphological formatives.
E.g. for Tira we might specify `[fv_class=aɔ]` then have a rule for imperfective itive that suffixes *-à* to roots bearing this feature tag.
Or we might specify a noun as `[sg_class=ð][pl_class=j]`, then we have a rule for singular that prefixes *ð-* and plural *j-* depending on the tag.

## Important note

This is a complicated issue where different design choices may have cascading impacts both on the application infrastructure as well as on memory and runtime complexity.
Rather than charging ahead, it's worth to plan out carefully, set up unit tests and profiling, and proceed slowly.

## FST operation

I'm not aware of any way to 'edit' a rule's context after it's been compiled to a WFST.
Best might be to prepend `f"{feature_str}[BOW]<Sigma>*` to the left context then re-compile.
We need to account for the following cases:

- [ ] Simple/string map rule: Create a new rule, recycling the Tau and prepending the new condition to `left_context`
- [ ] Sequence of rules: do the above for each rule in the sequence
- [ ] Prefix/suffix: Same as first case

We also don't want to assume the lexical features will EXACTLY match the feature string provided.
If a single feature is provided, then `"[feature=value]<Sigma>*[BOW]<Sigma>*"` is fine.
Otherwise, we need to cyclically insert `<Sigma>*` e.g. "`[class_marker=j]<Sigma>*[fv_class=aɔ]<Sigma>*[BOW]<Sigma>*`"

- This may result in a pretty hairy graph composition, but it'll have to do.

## Backend

Support conditioning morphological operations on the presence of lexical features

- [ ] `Paradigm` class prepends `[feature=value]` to each root for each lexically specified feature
  - [x] Function `Paradigm.get_lexical_feature_transducer()` returns FST mapping e.g. vəlɛð -> vəlɛð[aɔ]
  - [ ] Should apply before any other processes [TODO] continue from here!
  - [ ] Order of application: `input_str -> (principal part transducer ->) lexical feature insertion -> other marker rules`
- [x] `Marker` class supports an attr `Rule.lexical_features: Dict[str,str]`.
  - [x] If present, `FstRegistry` will pass `l=f"{feature_string}[BOW]<Sigma>*` to respective rule builder
  - ![ ] Use `fst_utils.stringify_feature_dict` to ensure consistent `Dict<-->str` mapping
  - [x] Extract function `feature_context_acceptor` in `FstRegistry`
  - [x] Inject logic to `FstRegistry._parse_rule`, `FstRegistry.prefix` and `FstRegistry.suffix`
    - [x] `Suffix` and `Prefix` objects take options `**_rule_kwargs`, that way we can pass `left_context=f"{feature_str}<Sigma>*"`
    - [x] FstRegistry first checks if feature symbols are present in inventory, if not throws error that GrammarRegistry needs to add feature symbols
    - [x] Add validation step to paradigm registry: every rule/marker with a lexical feature should correspond to a lexical feature marked by the Lexicon class

## Frontend

- [ ] User prompted to input features in format [feature=value, feature=value, feature=value]
  - Note: slightly different than canonical feature string format, but more readable for users
  - Serialization is easy: replace ', ' -> '][' then use `serialize_fst_string`
  - [ ] Populate defaults from feature registry
- [ ] Inflect interface:
  - [ ] Display lexical features for each root in dropdown
  - [ ] Allow user to input lexical features when typing in root to text field
