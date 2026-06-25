# Stage config

## Part 1: Order -> Stage rename

Rename all instances of "order" to "stage" (and change flavortext as appropriate for naturalness).
Each marker is associated with a single Stage, and each Paradigm gives an ordered list of Stages.

- [ ] Rename order -> stage
- [ ] Fix flavor text

## Part 2: Stages config

Create a new `Stages` config.
It's data is a list of dicts with keys `name` and `description`.

```yaml
kind: Stages
data:
    - name: inner_suffixation
      description: suffixes that attach close to the stem marking TAM, voice, deixis
    - name: tone_assignment
      description: assigning tone to the verb stem
    - name: outer_suffixation
      description: suffixes that attach after inner suffixes, marking participant person and number
```

Need to implement `StageList` and `StageListRegistry` as Python classes following other examples in the [registry folder](../src/grammar/registry/).
Logic is simple:

```python
@dataclass
class StageList:
    stages: list[dict[str, str]] = field(defaultfactory=list)

    def from_config() -> "Stagelist":
        ...

class StageListRegistry(Registry):
    def __init__():
        super.__init__(kind="StageList")

    def load_all_configs():
        ...
```

- [ ] Implement StageList
- [ ] Implement StageListRegistry

## Part 3: Backend refactor

...

## Part 4: Frontend refactor
