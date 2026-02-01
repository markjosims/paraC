# rules
YAML files defining phonological rules used in Tira parser.
Rules conform to the following YAML schema:
```yaml
rule:
    input_pattern: "fst_string"
    output_pattern: "fst_string"
    left_context: "fst_string"
    right_context: "fst_string"
    direction: "ltr" OR "rtl" or "sim"
    sigma_star: "fst_string"
rule:
    rule_sequence: ["rule_name", "rule_name"]
```
That is, the rule may directly define the input to the `pynini.cdrewrite` function, or it may contain a list of other rules to be applied