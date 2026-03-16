# rules
Config files defining phonological rules and patterns.
A rule is a Finite State Transducer (FST) expressing a context-sensitive change in the spirit of Sound Patterns of English, or a sequence of such changes.
Rules conform to the following YAML schema:
```yaml
kind: Rules
rules:
    simple_rule:
        input_pattern: "pattern string"
        output_pattern: "pattern string"
        left_context: "pattern string"
        right_context: "pattern string"
        direction: "ltr" OR "rtl" or "sim"
        sigma_star: "pattern string"
    map_rule:
        string_map:
            - ["pattern string", "pattern string"]
            - ["pattern string", "pattern string"]
            - ["pattern string", "pattern string"]
            ...
        left_context: "pattern string"
        right_context: "pattern string"
        ...
    chain_of_rules:
        rule_sequence: ["$rule_name", "$rule_name"]
        left_context: "pattern string"
        right_context: "pattern string"
```
That is, the rule may directly define the input to the `pynini.cdrewrite` function, or it may contain a list of other rules to be applied.
If it is a list of rules, the rules will be combined via composition, i.e. \Sigma* @ Rule1 @ Rule2...